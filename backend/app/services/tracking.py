"""Order tracking: where each lot is, in what order the van collects them, and how far along it is."""
from __future__ import annotations

from sqlmodel import Session, select

from app.models import Listing, Org, Pool, PoolItem, utcnow
from app.services.geo import haversine_km

VAN_SPEED_KMPH = 18.0      # city average, including traffic
MINUTES_PER_STOP = 8.0

STAGES = ["reserved", "confirmed", "out_for_pickup", "delivered"]


def route_order(stops: list[dict], buyer: Org) -> list[dict]:
    """Nearest-neighbour route: start at the stop furthest from the buyer, then always hop to the
    closest remaining stop, so the van ends up next to the buyer for the drop-off."""
    remaining = list(stops)
    if not remaining:
        return []
    current = max(remaining, key=lambda s: s["distance_km"])
    ordered = [current]
    remaining.remove(current)
    while remaining:
        nxt = min(remaining, key=lambda s: haversine_km(current["lat"], current["lng"], s["lat"], s["lng"]))
        ordered.append(nxt)
        remaining.remove(nxt)
        current = nxt
    return ordered


def tracking(session: Session, pool: Pool) -> dict:
    buyer = session.get(Org, pool.buyer_id)
    items = session.exec(select(PoolItem).where(PoolItem.pool_id == pool.id)).all()

    stops = []
    for item in items:
        li = session.get(Listing, item.listing_id)
        seller = session.get(Org, li.seller_id)
        stops.append({
            "listing_id": li.id, "title": li.title, "seller": seller.name, "seller_verified": seller.verified,
            "lat": li.lat, "lng": li.lng, "distance_km": item.distance_km,
            "quantity": item.quantity, "unit": li.unit, "line_total": item.line_total,
            "color_hex": li.measured_color_hex,
            "collected": item.picked_up_at is not None, "picked_up_at": item.picked_up_at,
        })
    stops = route_order(stops, buyer)
    for i, s in enumerate(stops, 1):
        s["stop_no"] = i

    legs = 0.0
    for a, b in zip(stops, stops[1:]):
        legs += haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])
    if stops:
        legs += stops[-1]["distance_km"]          # last stop to the buyer
    collected = sum(1 for s in stops if s["collected"])
    remaining_stops = len(stops) - collected

    stage = pool.status if pool.status in STAGES else pool.status
    if pool.status == "confirmed" and collected:
        stage = "out_for_pickup"
    eta_minutes = None
    if stage in ("confirmed", "out_for_pickup") and stops:
        eta_minutes = round(legs / VAN_SPEED_KMPH * 60 + remaining_stops * MINUTES_PER_STOP)

    return {
        "pool_id": pool.id, "status": pool.status, "stage": stage,
        "buyer": {"name": buyer.name, "lat": buyer.lat, "lng": buyer.lng},
        "stops": stops,
        "collected": collected, "total_stops": len(stops),
        "progress_pct": round(100 * collected / len(stops)) if stops else 0,
        "route_km": round(legs, 1), "eta_minutes": eta_minutes,
        "timeline": [
            {"key": "reserved", "label": "Lots reserved", "at": pool.created_at, "done": True},
            {"key": "confirmed", "label": "Order confirmed", "at": pool.confirmed_at,
             "done": pool.status in ("confirmed", "out_for_pickup", "delivered")},
            {"key": "out_for_pickup", "label": f"Collecting {len(stops)} lot{'s' if len(stops) != 1 else ''}",
             "at": min((s["picked_up_at"] for s in stops if s["picked_up_at"]), default=None),
             "done": collected > 0},
            {"key": "delivered", "label": "Delivered to you", "at": pool.delivered_at,
             "done": pool.status == "delivered"},
        ],
        "money": {"subtotal": pool.subtotal, "pickup_fee": pool.pickup_fee,
                  "platform_fee": pool.platform_fee, "total": pool.total},
        "quantity": pool.quantity, "unit": pool.unit,
        "generated_at": utcnow(),
    }
