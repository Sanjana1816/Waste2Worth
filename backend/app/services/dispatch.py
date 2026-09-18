"""Food rescue dispatch: alert the nearest verified NGOs by phone, and post to Vakh."""
from __future__ import annotations

import logging
from datetime import timezone

import httpx
from sqlmodel import Session, select

from app.config import settings
from app.models import DispatchLog, Listing, Org, OrgRole
from app.services import vakh, voice
from app.services.geo import haversine_km

log = logging.getLogger(__name__)
MAX_NGO_DISTANCE_KM = 10.0


def nearest_ngos(session: Session, listing: Listing, limit: int) -> list[tuple[Org, float]]:
    ngos = session.exec(select(Org).where(Org.role == OrgRole.ngo, Org.verified == True)).all()  # noqa: E712
    ranked = []
    for ngo in ngos:
        if ngo.accepts_categories and listing.category not in ngo.accepts_categories:
            continue
        d = haversine_km(listing.lat, listing.lng, ngo.lat, ngo.lng)
        if d <= MAX_NGO_DISTANCE_KM:
            ranked.append((ngo, round(d, 1)))
    ranked.sort(key=lambda x: x[1])
    return ranked[:limit]


async def dispatch_food(session: Session, listing: Listing) -> list[DispatchLog]:
    seller = session.get(Org, listing.seller_id)
    pickup_ist = listing.pickup_by.replace(tzinfo=timezone.utc).astimezone(voice.IST).strftime("%I:%M %p") \
        if listing.pickup_by else "soon"
    logs: list[DispatchLog] = []

    for ngo, dist in nearest_ngos(session, listing, settings.ngo_dispatch_count):
        variables = {"dish": (listing.attributes or {}).get("dish_name", listing.title),
                     "plates": f"{listing.quantity_available:g} {listing.unit}", "restaurant": seller.name,
                     "distance_km": dist, "pickup_by": pickup_ist, "ngo": ngo.name}
        script = (f"Hi {ngo.name}, this is Waste2Worth. {seller.name}, {dist} km from you, has "
                  f"{variables['plates']} of {variables['dish']} ready for pickup before {pickup_ist}. "
                  f"Press 1 or say yes to claim it.")
        try:
            if not ngo.phone:
                raise voice.NotConfigured("NGO has no phone number")
            res = await voice.call_ngo(ngo.phone, variables)
            entry = DispatchLog(listing_id=listing.id, org_id=ngo.id, channel="voice_call", status="sent",
                                detail=f"call {res.get('callSid') or res.get('conversation_id') or ''}".strip())
        except voice.NotConfigured as e:
            entry = DispatchLog(listing_id=listing.id, org_id=ngo.id, channel="voice_call", status="simulated",
                                detail=f"{script} [not actually called: {e}]")
        except httpx.HTTPError as e:
            entry = DispatchLog(listing_id=listing.id, org_id=ngo.id, channel="voice_call", status="failed",
                                detail=str(e)[:300])
        session.add(entry)
        logs.append(entry)

    try:
        res = await vakh.publish_food(listing, seller.name, pickup_ist)
        post_id = str((res.get("structuredContent") or {}).get("id") or "")
        listing.vakh_post_id = post_id or listing.vakh_post_id
        session.add(listing)
        entry = DispatchLog(listing_id=listing.id, channel="vakh", status="sent", detail=f"post {post_id}")
    except vakh.NotConfigured as e:
        entry = DispatchLog(listing_id=listing.id, channel="vakh", status="simulated", detail=str(e))
    except (vakh.VakhError, httpx.HTTPError) as e:
        entry = DispatchLog(listing_id=listing.id, channel="vakh", status="failed", detail=str(e)[:300])
    session.add(entry)
    logs.append(entry)
    session.commit()
    for entry in logs:
        session.refresh(entry)
    return logs
