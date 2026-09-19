"""An account's own view: everything they listed, sold, bought or claimed."""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.catalog import get_spec
from app.db import get_session
from app.models import Claim, Listing, ListingStatus, Org, Pool, PoolItem
from app.routers.listings import _out
from app.services import impact, listings as svc, pooling

router = APIRouter(prefix="/api/orgs", tags=["accounts"])

@router.get("/{org_id}/dashboard")
def dashboard(org_id: int, session: Session = Depends(get_session)):
    org = session.get(Org, org_id)
    if not org:
        raise HTTPException(404, "account not found")
    svc.expire_stale_food(session)
    pooling.release_expired(session)

    mine = session.exec(select(Listing).where(Listing.seller_id == org_id).order_by(Listing.created_at.desc())).all()
    listings = []
    for li in mine:
        d = _out(session, li)
        if li.status == ListingStatus.draft:
            d["readiness"] = svc.readiness(session, get_spec(li.category), li)
        listings.append(d)
    my_ids = {li.id for li in mine}
    titles = {li.id: li.title for li in mine}

    # Orders other people placed on my listings (one row per lot in a pool)
    sales = []
    if my_ids:
        rows = session.exec(select(PoolItem, Pool).where(PoolItem.pool_id == Pool.id,
                                                          PoolItem.listing_id.in_(my_ids))).all()
        for item, pool in rows:
            if pool.status in ("cancelled", "expired"):
                continue
            li = next(x for x in mine if x.id == item.listing_id)
            sales.append({"pool_id": pool.id, "listing_id": item.listing_id, "title": titles[item.listing_id],
                          "buyer": session.get(Org, pool.buyer_id).name, "quantity": item.quantity, "unit": li.unit,
                          "amount": item.line_total, "status": pool.status, "pooled": not pool.pool_key.startswith("listing:"),
                          "created_at": pool.created_at})

    # NGO claims on my donations
    claims_received = []
    if my_ids:
        for c in session.exec(select(Claim).where(Claim.listing_id.in_(my_ids))).all():
            li = next(x for x in mine if x.id == c.listing_id)
            claims_received.append({"claim_id": c.id, "listing_id": c.listing_id, "title": titles[c.listing_id],
                                    "ngo": session.get(Org, c.org_id).name, "quantity": c.quantity, "unit": li.unit,
                                    "status": c.status, "created_at": c.created_at})

    # What I bought or claimed
    purchases = []
    for pool in session.exec(select(Pool).where(Pool.buyer_id == org_id).order_by(Pool.created_at.desc())).all():
        items = session.exec(select(PoolItem).where(PoolItem.pool_id == pool.id)).all()
        first = session.get(Listing, items[0].listing_id) if items else None
        purchases.append({"pool_id": pool.id, "title": first.title if first else "Order", "sellers": len(items),
                          "quantity": pool.quantity, "unit": pool.unit, "total": pool.total, "status": pool.status,
                          "reserved_until": pool.reserved_until, "created_at": pool.created_at})
    claims_made = []
    for c in session.exec(select(Claim).where(Claim.org_id == org_id).order_by(Claim.created_at.desc())).all():
        li = session.get(Listing, c.listing_id)
        claims_made.append({"claim_id": c.id, "listing_id": li.id, "title": li.title, "donor": session.get(Org, li.seller_id).name,
                            "quantity": c.quantity, "unit": li.unit, "status": c.status, "pickup_by": li.pickup_by})

    earned = sum(s["amount"] for s in sales if s["status"] == "confirmed")
    co2 = 0.0
    for s in sales:
        if s["status"] == "confirmed":
            li = next(x for x in mine if x.id == s["listing_id"])
            co2 += impact.co2_saved_kg(get_spec(li.category), li.model_dump(), s["quantity"])
    for c in claims_received:
        li = next(x for x in mine if x.id == c["listing_id"])
        co2 += impact.co2_saved_kg(get_spec(li.category), li.model_dump(), c["quantity"])

    return {
        "org": org,
        "totals": {
            "live": sum(1 for li in mine if li.status == ListingStatus.published),
            "drafts": sum(1 for li in mine if li.status == ListingStatus.draft),
            "earned_inr": round(earned, 0),
            "co2e_avoided_kg": round(co2, 1),
            "orders": len([s for s in sales if s["status"] == "confirmed"]),
            "claims": len(claims_received),
        },
        "listings": listings, "sales": sales, "claims_received": claims_received,
        "purchases": purchases, "claims_made": claims_made,
    }
