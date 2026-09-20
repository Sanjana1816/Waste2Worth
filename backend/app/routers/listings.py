import io
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from PIL import UnidentifiedImageError
from sqlmodel import Session, select

from app.catalog import BRAND_SECOND_ATTRS, CATEGORIES, DEFECT_SHOT, get_spec
from app.config import settings
from app.db import get_session
from app.models import Listing, ListingImage, ListingStatus, Org, OrgRole
from app.schemas import ListingCreate, ListingUpdate
from app.services import dispatch, imaging, listings as svc, storage, vision
from app.services.geo import haversine_km
from app.services.validation import ValidationFailed

router = APIRouter(prefix="/api", tags=["listings"])


# ---------- catalogue ----------

@router.get("/categories")
def list_categories():
    return [{"key": s.key, "label": s.label, "group": s.group, "routes": s.routes, "units": s.units,
             "min_images": s.min_images, "poolable": s.poolable, "perishable": s.perishable}
            for s in CATEGORIES.values()]


@router.get("/categories/{key}")
def category_form(key: str):
    """Everything the frontend needs to render the listing form for this category."""
    spec = get_spec(key)
    if not spec:
        raise HTTPException(404, "unknown category")
    out = spec.to_public()
    out["brand_second_extras"] = None if spec.perishable else {
        "attributes": [a.__dict__ for a in BRAND_SECOND_ATTRS], "shots": [DEFECT_SHOT.__dict__],
        "requires": ["brand", "product_name", "model_sku", "new_price_per_unit"],
    }
    return out


# ---------- helpers ----------

def _get(session: Session, listing_id: int) -> tuple[Listing, object]:
    li = session.get(Listing, listing_id)
    if not li:
        raise HTTPException(404, "listing not found")
    return li, get_spec(li.category)


def _out(session: Session, li: Listing, lat: float | None = None, lng: float | None = None) -> dict:
    seller = session.get(Org, li.seller_id)
    images = session.exec(select(ListingImage).where(ListingImage.listing_id == li.id)).all()
    d = li.model_dump()
    d["available"] = max(0.0, li.quantity_available - li.quantity_reserved)
    d["seller"] = {"id": seller.id, "name": seller.name, "verified": seller.verified, "badges": seller.badges}
    maps = (li.ai_summary or {}).get("defect_map") or {}
    d["images"] = [{"id": i.id, "shot_type": i.shot_type, "url": storage.url(i.path),
                    "quality_ok": i.quality_ok, "color_hex": i.color_hex,
                    "defect_map": maps.get(str(i.id))} for i in images]
    if lat is not None and lng is not None:
        d["distance_km"] = round(haversine_km(lat, lng, li.lat, li.lng), 1)
    return d


# ---------- listings ----------

@router.post("/listings", status_code=201)
def create_listing(body: ListingCreate, session: Session = Depends(get_session)):
    spec = get_spec(body.category)
    if not spec:
        raise HTTPException(404, "unknown category")
    seller = session.get(Org, body.seller_id)
    if not seller:
        raise HTTPException(404, "seller not found")
    if body.source_type == "brand_second" and seller.role != OrgRole.brand:
        raise HTTPException(403, "only brand accounts can list brand seconds")
    data = body.model_dump()
    data["lat"] = body.lat if body.lat is not None else seller.lat
    data["lng"] = body.lng if body.lng is not None else seller.lng
    li = Listing(**data, quantity_available=body.quantity or 0)
    svc.validate_and_enrich(spec, li)
    session.add(li)
    session.commit()
    session.refresh(li)
    return {"listing": _out(session, li), "readiness": svc.readiness(session, spec, li)}


@router.patch("/listings/{listing_id}")
def update_listing(listing_id: int, body: ListingUpdate, session: Session = Depends(get_session)):
    li, spec = _get(session, listing_id)
    if li.status != ListingStatus.draft:
        raise HTTPException(409, "only drafts can be edited; withdraw and relist instead")
    required = {"source_type", "title", "quantity", "unit", "condition", "reason_code", "reason_detail", "has_invoice", "attributes"}
    missing = [{"field": k, "message": "is required"} for k, v in body.model_dump(exclude_unset=True).items()
               if v is None and k in required]
    if missing:
        raise ValidationFailed(missing)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(li, k, v)
    if body.quantity is not None:
        li.quantity_available = body.quantity
        if "weight_kg" not in body.model_fields_set:
            li.weight_kg = None  # recompute from the new quantity
    svc.validate_and_enrich(spec, li)
    session.add(li)
    session.commit()
    session.refresh(li)
    return {"listing": _out(session, li), "readiness": svc.readiness(session, spec, li)}


@router.post("/listings/{listing_id}/images", status_code=201)
async def upload_image(listing_id: int, shot_type: str = Form(...), file: UploadFile = File(...),
                       session: Session = Depends(get_session)):
    li, spec = _get(session, listing_id)
    valid_shots = {s.key for s in spec.shots} | ({DEFECT_SHOT.key} if li.source_type == "brand_second" else set())
    if shot_type not in valid_shots:
        raise HTTPException(422, f"shot_type must be one of: {', '.join(sorted(valid_shots))}")
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"photo is larger than {settings.max_upload_mb} MB")
    try:
        img = imaging.open_image(data)
    except (UnidentifiedImageError, OSError):
        raise HTTPException(422, imaging.ISSUE_TEXT["unreadable"])
    result = imaging.analyze(img, shot_type)

    # Re-encode: strips EXIF (including the GPS location of the seller's home) and caps the size.
    img.thumbnail((2048, 2048))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    try:
        key = storage.save(f"{listing_id}/{shot_type}_{uuid.uuid4().hex[:10]}.jpg", buf.getvalue())
    except storage.StorageError as e:
        raise HTTPException(502, str(e))

    row = ListingImage(listing_id=listing_id, shot_type=shot_type, path=key, **result)
    session.add(row)
    session.commit()
    session.refresh(row)
    return {
        "image": {**row.model_dump(exclude={"path"}), "problems": imaging.describe_issues(row.issues)},
        "readiness": svc.readiness(session, spec, li),
    }


@router.post("/listings/{listing_id}/images/{image_id}/inspect")
async def inspect_image(listing_id: int, image_id: int, session: Session = Depends(get_session)):
    """Damage scan: the AI marks where the defects are on this photo, so buyers don't have to hunt."""
    li, spec = _get(session, listing_id)
    img = session.get(ListingImage, image_id)
    if not img or img.listing_id != listing_id:
        raise HTTPException(404, "photo not found on this listing")
    try:
        data = storage.read(img.path)
    except storage.StorageError as e:
        raise HTTPException(502, str(e))
    result = await vision.inspect(data, spec.label.lower())

    summary = dict(li.ai_summary or {})
    maps = dict(summary.get("defect_map") or {})
    maps[str(image_id)] = result.model_dump()
    summary["defect_map"] = maps
    li.ai_summary = summary
    session.add(li)
    session.commit()
    return {"image_id": image_id, "shot_type": img.shot_type, **result.model_dump()}


@router.get("/listings/{listing_id}/readiness")
def get_readiness(listing_id: int, session: Session = Depends(get_session)):
    li, spec = _get(session, listing_id)
    return svc.readiness(session, spec, li)


@router.post("/listings/{listing_id}/publish")
async def publish_listing(listing_id: int, session: Session = Depends(get_session)):
    li, spec = _get(session, listing_id)
    if li.status != ListingStatus.draft:
        raise HTTPException(409, f"listing is already {li.status.value}")
    state = svc.publish(session, spec, li)
    if not state["ready"]:
        raise HTTPException(409, {"message": "Not ready to publish yet", "readiness": state})
    out = {"listing": _out(session, li)}
    if spec.perishable:
        logs = await dispatch.dispatch_food(session, li)
        out["dispatch"] = [log.model_dump() for log in logs]
    return out


@router.post("/listings/{listing_id}/withdraw")
def withdraw(listing_id: int, session: Session = Depends(get_session)):
    li, _ = _get(session, listing_id)
    if li.quantity_reserved > 0:
        raise HTTPException(409, "part of this lot is reserved in a pooled order")
    li.status = ListingStatus.withdrawn
    session.add(li)
    session.commit()
    return {"ok": True}


@router.get("/listings")
def search_listings(
    category: str | None = None, route: str | None = None, source_type: str | None = None,
    q: str | None = None, lat: float | None = None, lng: float | None = None,
    radius_km: float = Query(default=25, le=200), limit: int = Query(default=50, le=200),
    session: Session = Depends(get_session),
):
    svc.expire_stale_food(session)
    stmt = select(Listing).where(Listing.status == ListingStatus.published)
    if category:
        stmt = stmt.where(Listing.category == category)
    if route:
        stmt = stmt.where(Listing.route == route)
    if source_type:
        stmt = stmt.where(Listing.source_type == source_type)
    rows = session.exec(stmt.order_by(Listing.published_at.desc())).all()
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in " ".join(
            str(x or "") for x in (r.title, r.description, r.brand, r.model_sku, r.manufacturer_color)).lower()]
    out = [_out(session, r, lat, lng) for r in rows]
    if lat is not None and lng is not None:
        out = sorted((o for o in out if o["distance_km"] <= radius_km), key=lambda o: o["distance_km"])
    return out[:limit]


@router.get("/listings/{listing_id}")
def get_listing(listing_id: int, session: Session = Depends(get_session)):
    li, spec = _get(session, listing_id)
    out = _out(session, li)
    if li.status == ListingStatus.draft:
        out["readiness"] = svc.readiness(session, spec, li)
    return out


@router.get("/listings/{listing_id}/matches")
def matches(listing_id: int, limit: int = 10, session: Session = Depends(get_session)):
    """Who nearby can use this: buyers for resell, recyclers for recycle, NGOs for donate."""
    li, spec = _get(session, listing_id)
    roles = {"resell": [OrgRole.buyer, OrgRole.business], "reuse": [OrgRole.buyer, OrgRole.individual, OrgRole.ngo],
             "recycle": [OrgRole.recycler], "donate": [OrgRole.ngo]}[li.route]
    orgs = session.exec(select(Org).where(Org.role.in_(roles), Org.id != li.seller_id)).all()
    ranked = []
    for org in orgs:
        if org.accepts_categories and li.category not in org.accepts_categories:
            continue
        # A business is only a buyer for categories it has said it uses (a restaurant doesn't want tiles).
        if org.role == OrgRole.business and li.category not in (org.accepts_categories or []):
            continue
        if li.route == "recycle" and spec.key == "electronics" and not org.certified_recycler:
            continue
        if li.route == "donate" and not org.verified:
            continue
        d = haversine_km(li.lat, li.lng, org.lat, org.lng)
        ranked.append({"org_id": org.id, "name": org.name, "role": org.role, "verified": org.verified,
                       "certified_recycler": org.certified_recycler, "distance_km": round(d, 1),
                       "specialist": bool(org.accepts_categories)})
    ranked.sort(key=lambda m: (not m["specialist"], m["distance_km"]))
    return {"route": li.route, "matches": ranked[:limit]}
