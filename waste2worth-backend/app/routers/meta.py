import hashlib
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.catalog import get_spec
from app.config import settings
from app.db import get_session
from app.models import Claim, Listing, Org, Pool, PoolItem
from app.schemas import OrgCreate
from app.services import impact, vakh

router = APIRouter(prefix="/api", tags=["orgs, impact, integrations"])


@router.get("/orgs")
def list_orgs(role: str | None = None, session: Session = Depends(get_session)):
    stmt = select(Org)
    if role:
        stmt = stmt.where(Org.role == role)
    return session.exec(stmt).all()


@router.post("/orgs", status_code=201)
def create_org(body: OrgCreate, session: Session = Depends(get_session)):
    org = Org(**body.model_dump())   # new orgs start unverified; an admin verifies NGOs and recyclers
    session.add(org)
    session.commit()
    session.refresh(org)
    return org


def _completed(session: Session, seller_id: int | None = None):
    """Yield (listing, quantity moved) for every confirmed pool item and every claim."""
    rows = session.exec(select(PoolItem, Pool, Listing).where(
        PoolItem.pool_id == Pool.id, Pool.status == "confirmed", PoolItem.listing_id == Listing.id)).all()
    for item, _, li in rows:
        if seller_id is None or li.seller_id == seller_id:
            yield li, item.quantity, item.line_total
    for c, li in session.exec(select(Claim, Listing).where(Claim.listing_id == Listing.id,
                                                             Claim.status != "cancelled")).all():
        if seller_id is None or li.seller_id == seller_id:
            yield li, c.quantity, 0.0


def _totals(session: Session, seller_id: int | None = None) -> dict:
    kg = co2 = value = 0.0
    meals = 0
    for li, qty, money in _completed(session, seller_id):
        spec = get_spec(li.category)
        data = li.model_dump()
        share = qty / li.quantity if li.quantity else 0
        kg += (li.weight_kg or 0) * share
        co2 += impact.co2_saved_kg(spec, data, qty)
        meals += impact.meals(spec, li.unit, qty)
        value += money
    return {"kg_diverted": round(kg, 1), "co2e_avoided_kg": round(co2, 1), "meals_rescued": meals,
            "value_recovered_inr": round(value, 0)}


@router.get("/impact/summary")
def impact_summary(session: Session = Depends(get_session)):
    return _totals(session)


@router.get("/impact/orgs/{org_id}/certificate")
def certificate(org_id: int, session: Session = Depends(get_session)):
    """Impact certificate a donor or seller can attach to CSR / ESG reporting."""
    org = session.get(Org, org_id)
    if not org:
        raise HTTPException(404, "org not found")
    totals = _totals(session, org_id)
    recipients = sorted({session.get(Org, c.org_id).name for c, li in session.exec(
        select(Claim, Listing).where(Claim.listing_id == Listing.id, Listing.seller_id == org_id)).all()})
    serial = hashlib.sha1(f"{org.id}:{totals}".encode()).hexdigest()[:10].upper()
    return {"certificate_no": f"W2W-{org.id:04d}-{serial}", "org": org.name, **totals,
            "recipients": recipients,
            "method": "CO2e uses per-material emission factors, credited fully for reuse and at 40% for recycling. "
                      "These are estimates, not audited figures."}


@router.get("/integrations/status")
def integrations():
    return {
        "vision_provider": settings.vision_provider,
        "gemini": bool(settings.gemini_api_key),
        "elevenlabs": bool(settings.elevenlabs_api_key),
        "elevenlabs_calls": bool(settings.elevenlabs_agent_id and settings.elevenlabs_phone_number_id),
        "vakh_connected": Path(settings.vakh_token_file).exists(),
        "vakh_post_tool": settings.vakh_post_tool,
    }


@router.get("/integrations/vakh/tools")
async def vakh_tools():
    """Lists Vakh's MCP tools and their input schemas, so you can pick VAKH_POST_TOOL."""
    try:
        return await vakh.list_tools()
    except vakh.NotConfigured as e:
        raise HTTPException(503, str(e))
    except (vakh.VakhError, httpx.HTTPError) as e:
        raise HTTPException(502, f"Vakh error: {e}")
