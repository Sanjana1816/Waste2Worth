"""Pooled lots: combine identical stock from several sellers into one order.

Identical means: same category, same unit and every `pool_keys` value equal after
normalising (brand, SKU/design code, manufacturer colour name, size, finish...).
For colour-critical categories the lighting-corrected colour of each lot must also be
within `pool_max_delta_e` of the reference lot, so a different batch/shade is excluded.
"""
from __future__ import annotations

import re
from datetime import timedelta

from fastapi import HTTPException
from sqlmodel import Session, select

from app.catalog import CategorySpec, get_spec
from app.config import settings
from app.models import Listing, ListingStatus, Org, Pool, PoolItem, utcnow
from app.schemas import PoolRequest
from app.services import valuation
from app.services.geo import haversine_km
from app.services.imaging import delta_e

LISTING_COLUMNS = {"brand", "model_sku", "manufacturer_color", "product_name"}


def norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def pool_key(spec: CategorySpec, fields: dict, attrs: dict) -> str | None:
    parts = []
    for k in spec.pool_keys:
        v = fields.get(k) if k in LISTING_COLUMNS else attrs.get(k)
        if v in (None, ""):
            return None
        parts.append(norm(v))
    return spec.key + "|" + "|".join(parts)


def listing_pool_key(spec: CategorySpec, listing: Listing) -> str | None:
    return pool_key(spec, listing.model_dump(), listing.attributes or {})


def available(listing: Listing) -> float:
    return max(0.0, listing.quantity_available - listing.quantity_reserved)


def release_expired(session: Session) -> int:
    now = utcnow()
    stale = session.exec(select(Pool).where(Pool.status == "reserved", Pool.reserved_until < now)).all()
    for pool in stale:
        _release(session, pool, "expired")
    if stale:
        session.commit()
    return len(stale)


def _release(session: Session, pool: Pool, status: str) -> None:
    for item in session.exec(select(PoolItem).where(PoolItem.pool_id == pool.id)).all():
        listing = session.get(Listing, item.listing_id)
        listing.quantity_reserved = max(0.0, listing.quantity_reserved - item.quantity)
        session.add(listing)
    pool.status = status
    session.add(pool)


def quote(session: Session, req: PoolRequest) -> dict:
    buyer = session.get(Org, req.buyer_id)
    if not buyer:
        raise HTTPException(404, "buyer not found")
    radius = min(req.radius_km or settings.pool_max_radius_km, 50.0)

    ref_lab = None
    if req.listing_id:
        ref = session.get(Listing, req.listing_id)
        if not ref or ref.status != ListingStatus.published:
            raise HTTPException(404, "listing not found or not available")
        spec = get_spec(ref.category)
        if ref.route not in ("resell", "recycle"):
            raise HTTPException(400, "donations are claimed, not bought")
        # Poolable stock can be combined across sellers; anything else is a plain order for this one lot.
        pooled = spec.poolable and ref.route == "resell" and listing_pool_key(spec, ref) is not None
        key = listing_pool_key(spec, ref) if pooled else f"listing:{ref.id}"
        unit, ref_lab = ref.unit, ref.measured_color_lab
        ref_new_price = valuation.new_price_per_unit(spec, ref.model_dump())
    else:
        spec = get_spec(req.category or "")
        if not spec or not spec.poolable:
            raise HTTPException(400, "send a poolable category (e.g. tiles) or a listing_id")
        key = pool_key(spec, req.match, req.match)
        if not key:
            raise HTTPException(422, f"to find matching stock, also send: {', '.join(spec.pool_keys)}")
        unit = req.unit or spec.units[0]
        ref_new_price = None

    if key.startswith("listing:"):
        rows = [ref]
    else:
        rows = session.exec(select(Listing).where(
            Listing.category == spec.key, Listing.status == ListingStatus.published,
            Listing.route == "resell", Listing.unit == unit)).all()

    candidates, excluded = [], []
    for li in rows:
        if (not key.startswith("listing:") and listing_pool_key(spec, li) != key)                 or available(li) <= 0 or li.asking_price_per_unit is None:
            continue
        dist = haversine_km(buyer.lat, buyer.lng, li.lat, li.lng)
        if dist > radius:
            excluded.append({"listing_id": li.id, "reason": f"{dist:.1f} km away (limit {radius:g} km)"})
            continue
        candidates.append((li, dist))

    if spec.color_critical and not key.startswith("listing:"):
        with_color = [(li, d) for li, d in candidates if li.measured_color_lab]
        for li, _ in candidates:
            if not li.measured_color_lab:
                excluded.append({"listing_id": li.id, "reason": "no colour reference photo, so the shade can't be verified"})
        candidates = with_color
        if ref_lab is None and candidates:
            ref_lab = max(candidates, key=lambda c: available(c[0]))[0].measured_color_lab
        kept = []
        for li, d in candidates:
            de = delta_e(ref_lab, li.measured_color_lab)
            if de > settings.pool_max_delta_e:
                excluded.append({"listing_id": li.id, "reason": f"different shade/batch (colour difference ΔE {de})"})
            else:
                kept.append((li, d))
        candidates = kept

    candidates.sort(key=lambda c: (c[0].asking_price_per_unit, c[1]))
    need, items = req.quantity, []
    for li, dist in candidates:
        if need <= 0:
            break
        take = min(available(li), need)
        need -= take
        items.append({
            "listing_id": li.id, "seller_id": li.seller_id, "title": li.title,
            "quantity": take, "unit_price": li.asking_price_per_unit,
            "line_total": round(take * li.asking_price_per_unit, 2), "distance_km": round(dist, 1),
            "delta_e": delta_e(ref_lab, li.measured_color_lab) if spec.color_critical else None,
            "color_hex": li.measured_color_hex, "condition": li.condition,
        })
        if ref_new_price is None:
            ref_new_price = valuation.new_price_per_unit(spec, li.model_dump())

    allocated = req.quantity - max(need, 0)
    result = {
        "category": spec.key, "pool_key": key, "unit": unit, "requested": req.quantity,
        "allocated": allocated, "items": items, "excluded": excluded,
        "available_total": round(sum(available(li) for li, _ in candidates), 2),
    }
    if not items or need > 0:
        result.update(status="insufficient_stock",
                      message=f"Only {result['available_total']:g} {unit} of matching stock is within {radius:g} km.")
        return result

    subtotal = round(sum(i["line_total"] for i in items), 2)
    stops = len({i["seller_id"] for i in items})
    pickup = valuation.pickup_fee(stops, sum(i["distance_km"] for i in items))
    route = rows[0].route if key.startswith("listing:") else "resell"
    platform = round(valuation.commission(subtotal, route) + (valuation.POOL_FLAT_FEE if stops > 1 else 0), 2)
    total = round(subtotal + pickup + platform, 2)
    new_total = round(req.quantity * ref_new_price, 2) if ref_new_price else None
    des = [i["delta_e"] for i in items if i["delta_e"] is not None]
    result.update(
        status="ok", sellers=stops, subtotal=subtotal, pickup_fee=pickup, platform_fee=platform, total=total,
        new_price_total=new_total,
        savings_pct=round(100 * (1 - total / new_total), 1) if new_total else None,
        shade_match_pct=round(max(0.0, 100 - 5 * sum(des) / len(des)), 1) if des else None,
    )
    result["pooled"] = not key.startswith("listing:")
    if result["pooled"] and new_total and total >= 0.9 * new_total:
        result.update(status="not_worth_it",
                      message="After pickup and fees this costs almost as much as buying new, so we won't create this pool.")
    return result


def reserve(session: Session, req: PoolRequest) -> Pool:
    release_expired(session)
    q = quote(session, req)
    if q["status"] != "ok":
        raise HTTPException(409, q.get("message", q["status"]))
    # All-or-nothing: re-check every lot under lock before reserving any of it.
    locked = {}
    for item in q["items"]:
        li = session.exec(select(Listing).where(Listing.id == item["listing_id"]).with_for_update()).one()
        if available(li) + 1e-9 < item["quantity"]:
            session.rollback()
            raise HTTPException(409, "Some of this stock was just taken. Get a new quote.")
        locked[li.id] = li
    pool = Pool(
        buyer_id=req.buyer_id, category=q["category"], pool_key=q["pool_key"], quantity=req.quantity,
        unit=q["unit"], subtotal=q["subtotal"], pickup_fee=q["pickup_fee"], platform_fee=q["platform_fee"],
        total=q["total"], new_price_total=q["new_price_total"], savings_pct=q["savings_pct"],
        shade_match_pct=q["shade_match_pct"],
        reserved_until=utcnow() + timedelta(minutes=settings.pool_reservation_minutes),
    )
    session.add(pool)
    session.flush()
    for item in q["items"]:
        li = locked[item["listing_id"]]
        li.quantity_reserved += item["quantity"]
        session.add(li)
        session.add(PoolItem(pool_id=pool.id, listing_id=li.id, quantity=item["quantity"],
                             unit_price=item["unit_price"], line_total=item["line_total"],
                             distance_km=item["distance_km"], delta_e=item["delta_e"]))
    session.commit()
    session.refresh(pool)
    return pool


def confirm(session: Session, pool: Pool) -> Pool:
    release_expired(session)
    session.refresh(pool)
    if pool.status != "reserved":
        raise HTTPException(409, f"pool is {pool.status}")
    for item in session.exec(select(PoolItem).where(PoolItem.pool_id == pool.id)).all():
        li = session.get(Listing, item.listing_id)
        li.quantity_reserved = max(0.0, li.quantity_reserved - item.quantity)
        li.quantity_available = max(0.0, li.quantity_available - item.quantity)
        if li.quantity_available <= 0:
            li.status = ListingStatus.sold_out
        session.add(li)
    pool.status = "confirmed"
    pool.confirmed_at = utcnow()
    session.add(pool)
    session.commit()
    session.refresh(pool)
    return pool


def cancel(session: Session, pool: Pool) -> Pool:
    if pool.status != "reserved":
        raise HTTPException(409, f"pool is {pool.status}")
    _release(session, pool, "cancelled")
    session.commit()
    session.refresh(pool)
    return pool
