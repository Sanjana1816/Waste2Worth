import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.catalog import get_spec
from app.db import get_session
from app.models import Claim, DispatchLog, Listing, ListingStatus, Org, OrgRole, utcnow
from app.schemas import ClaimRequest
from app.services import dispatch, listings as svc, voice

router = APIRouter(prefix="/api", tags=["donations & food rescue"])


class ParseText(BaseModel):
    text: str = Field(min_length=3, max_length=500)


@router.post("/food/voice-draft")
async def voice_draft(seller_id: int = Form(...), audio: UploadFile = File(...),
                      session: Session = Depends(get_session)):
    """Restaurant speaks the listing, and we return a food draft to confirm (nothing is saved yet)."""
    seller = session.get(Org, seller_id)
    if not seller:
        raise HTTPException(404, "seller not found")
    try:
        stt = await voice.transcribe(await audio.read(), audio.filename or "clip.webm", audio.content_type)
    except voice.NotConfigured as e:
        raise HTTPException(503, f"{e}. Use /api/food/text-draft to test without ElevenLabs.")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"speech-to-text failed: {e}")
    return {"transcript": stt["text"], "language": stt["language"],
            "draft": {**voice.parse_food_text(stt["text"]), "seller_id": seller_id}}


@router.post("/food/text-draft")
def text_draft(body: ParseText):
    return {"transcript": body.text, "draft": voice.parse_food_text(body.text)}


@router.post("/listings/{listing_id}/dispatch")
async def redispatch(listing_id: int, session: Session = Depends(get_session)):
    """Alert NGOs again (e.g. nobody answered the first round)."""
    li = session.get(Listing, listing_id)
    if not li or li.status != ListingStatus.published or li.route != "donate":
        raise HTTPException(409, "only live donation listings can be dispatched")
    return [log.model_dump() for log in await dispatch.dispatch_food(session, li)]


@router.get("/listings/{listing_id}/dispatch")
def dispatch_log(listing_id: int, session: Session = Depends(get_session)):
    return session.exec(select(DispatchLog).where(DispatchLog.listing_id == listing_id)).all()


@router.post("/listings/{listing_id}/claim", status_code=201)
def claim(listing_id: int, body: ClaimRequest, session: Session = Depends(get_session)):
    """A verified NGO claims a free donation. First come, first served."""
    svc.expire_stale_food(session)
    li = session.get(Listing, listing_id)
    if not li:
        raise HTTPException(404, "listing not found")
    if li.route != "donate":
        raise HTTPException(409, "only donations can be claimed; use a pooled order to buy")
    if li.status != ListingStatus.published:
        raise HTTPException(409, f"this donation is {li.status.value}")
    org = session.get(Org, body.org_id)
    if not org or org.role != OrgRole.ngo or not org.verified:
        raise HTTPException(403, "only verified NGOs can claim donations")
    qty = body.quantity or li.quantity_available
    if qty > li.quantity_available + 1e-9:
        raise HTTPException(409, f"only {li.quantity_available:g} {li.unit} left")
    li.quantity_available -= qty
    if li.quantity_available <= 1e-9:
        li.quantity_available = 0
        li.status = ListingStatus.claimed
    c = Claim(listing_id=li.id, org_id=org.id, quantity=qty)
    session.add_all([li, c])
    session.commit()
    session.refresh(c)
    spec = get_spec(li.category)
    return {"claim": c, "remaining": li.quantity_available,
            "pickup_by": li.pickup_by, "message": f"{org.name} claimed {qty:g} {li.unit}. "
            f"{'Pick it up before the window closes.' if spec.perishable else 'Arrange pickup with the donor.'}"}


@router.post("/claims/{claim_id}/picked-up")
def picked_up(claim_id: int, session: Session = Depends(get_session)):
    c = session.get(Claim, claim_id)
    if not c:
        raise HTTPException(404, "claim not found")
    c.status, c.picked_up_at = "picked_up", utcnow()
    session.add(c)
    session.commit()
    session.refresh(c)
    return c
