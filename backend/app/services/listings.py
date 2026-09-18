"""Listing lifecycle: draft -> (photos) -> ready -> published -> sold_out / claimed / expired."""
from __future__ import annotations

from sqlmodel import Session, select

from app.catalog import DEFECT_SHOT, CategorySpec, Shot
from app.models import Listing, ListingImage, ListingStatus, utcnow
from app.services import impact, routing, valuation
from app.services.imaging import describe_issues
from app.services.validation import ValidationFailed, validate_listing


def validate_and_enrich(spec: CategorySpec, listing: Listing) -> Listing:
    """Validate the listing and fill in route, valuation and impact. Raises ValidationFailed."""
    data = listing.model_dump()
    suggestion = routing.recommend(spec, data)
    if not data.get("route"):
        data["route"] = suggestion["route"]
    clean, derived, errors = validate_listing(spec, data)
    if errors:
        raise ValidationFailed(errors)
    data["attributes"] = clean
    listing.route = data["route"]
    listing.attributes = clean
    listing.route_suggestion = suggestion
    if "pickup_by" in derived:
        listing.pickup_by = derived["pickup_by"]
    est = valuation.estimate(spec, data)
    listing.est_value_low, listing.est_value_high = est["low"], est["high"]
    listing.price_cap_per_unit = est["cap_per_unit"]
    listing.co2_saved_kg = impact.co2_saved_kg(spec, data)
    if not listing.weight_kg:
        listing.weight_kg = round(valuation.weight_kg(spec, data), 2)
    return listing


def required_shots(spec: CategorySpec, listing: Listing) -> list[Shot]:
    shots = [s for s in spec.shots if s.required]
    if listing.source_type == "brand_second":
        shots.append(DEFECT_SHOT)
    attrs = listing.attributes or {}
    if spec.key == "electronics" and attrs.get("working_status") in ("fully_working", "partially_working"):
        shots.append(spec.shot("powered_on"))
    return shots


def latest_images(session: Session, listing_id: int) -> dict[str, ListingImage]:
    imgs = session.exec(select(ListingImage).where(ListingImage.listing_id == listing_id)
                        .order_by(ListingImage.id)).all()
    latest: dict[str, ListingImage] = {}
    for img in imgs:
        latest[img.shot_type] = img
    return latest


def readiness(session: Session, spec: CategorySpec, listing: Listing) -> dict:
    latest = latest_images(session, listing.id)
    missing, retake = [], []
    for shot in required_shots(spec, listing):
        img = latest.get(shot.key)
        if img is None:
            missing.append({"shot": shot.key, "label": shot.label, "help": shot.help})
        elif not img.quality_ok:
            retake.append({"shot": shot.key, "label": shot.label, "problems": describe_issues(img.issues)})
    good = sum(1 for img in latest.values() if img.quality_ok)
    _, _, errors = validate_listing(spec, listing.model_dump())
    if listing.route == "resell" and not listing.asking_price_per_unit:
        errors.append({"field": "asking_price_per_unit", "message": "set a price per unit to resell"})
    if spec.perishable and listing.pickup_by and listing.pickup_by <= utcnow():
        errors.append({"field": "attributes.cooked_at", "message": "the pickup window has already closed"})
    return {
        "ready": not missing and not retake and not errors and good >= spec.min_images,
        "missing_shots": missing, "retake_shots": retake,
        "image_count": good, "min_images": spec.min_images, "field_errors": errors,
    }


def publish(session: Session, spec: CategorySpec, listing: Listing) -> dict:
    state = readiness(session, spec, listing)
    if not state["ready"]:
        return state
    ref = latest_images(session, listing.id).get("color_reference")
    if ref is not None and ref.white_balanced:
        listing.measured_color_hex, listing.measured_color_lab = ref.color_hex, ref.color_lab
    listing.status = ListingStatus.published
    listing.published_at = utcnow()
    session.add(listing)
    session.commit()
    session.refresh(listing)
    return state


def expire_stale_food(session: Session) -> int:
    now = utcnow()
    stale = session.exec(select(Listing).where(Listing.status == ListingStatus.published,
                                               Listing.pickup_by != None, Listing.pickup_by < now)).all()  # noqa: E711
    for li in stale:
        li.status = ListingStatus.expired
        session.add(li)
    if stale:
        session.commit()
    return len(stale)
