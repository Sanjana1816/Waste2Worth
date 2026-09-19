"""Validates a listing against its category spec and the platform's trust rules."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.catalog import (
    BRAND_SECOND_ATTRS, DATA_BEARING_DEVICES, FOOD_MAX_HOURS, PROVENANCE_FIELDS, Attr, CategorySpec,
)
from app.models import utcnow
from app.services import valuation

MIN_REASON_CHARS = 15
MIN_OTHER_REASON_CHARS = 25


class ValidationFailed(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__("; ".join(f"{e['field']}: {e['message']}" for e in errors))


def parse_dt(value) -> datetime:
    """Parse ISO datetimes; return naive UTC (the DB convention)."""
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _coerce(attr: Attr, value):
    if attr.type == "text":
        s = str(value).strip()
        if not s:
            raise ValueError("cannot be empty")
        return s
    if attr.type == "int":
        if isinstance(value, bool):
            raise ValueError("must be a whole number")
        return int(value)
    if attr.type == "number":
        if isinstance(value, bool):
            raise ValueError("must be a number")
        v = float(value)
        if v < 0:
            raise ValueError("cannot be negative")
        return v
    if attr.type == "bool":
        if isinstance(value, bool):
            return value
        if str(value).lower() in ("true", "yes", "1"):
            return True
        if str(value).lower() in ("false", "no", "0"):
            return False
        raise ValueError("must be yes or no")
    if attr.type == "enum":
        v = str(value).strip().lower()
        if v not in attr.options:
            raise ValueError(f"must be one of: {', '.join(attr.options)}")
        return v
    if attr.type == "datetime":
        return parse_dt(value).isoformat()
    raise ValueError("unsupported type")


def expected_attributes(spec: CategorySpec, source_type: str) -> tuple[Attr, ...]:
    return spec.attributes + (BRAND_SECOND_ATTRS if source_type == "brand_second" else ())


def validate_listing(spec: CategorySpec, data: dict, now: datetime | None = None) -> tuple[dict, list[dict]]:
    """Return (clean attributes, derived fields such as pickup_by, errors) for a merged listing dict."""
    now = now or utcnow()
    errors: list[dict] = []

    def err(field: str, msg: str) -> None:
        errors.append({"field": field, "message": msg})

    source_type = data.get("source_type") or "business_surplus"
    route = data.get("route")

    if data.get("unit") not in spec.units:
        err("unit", f"must be one of: {', '.join(spec.units)}")
    if route and route not in spec.routes:
        err("route", f"{spec.label} can only go to: {', '.join(spec.routes)}")

    # --- why is it waste? ---
    reason_keys = {r.key for r in spec.reasons}
    reason = data.get("reason_code")
    detail = (data.get("reason_detail") or "").strip()
    if reason not in reason_keys:
        err("reason_code", f"pick one of: {', '.join(sorted(reason_keys))}")
    need = MIN_OTHER_REASON_CHARS if reason == "other" else MIN_REASON_CHARS
    if len(detail) < need:
        err("reason_detail", f"tell buyers why this is being given away or sold (at least {need} characters)")

    # --- provenance ---
    required_prov = set(spec.provenance_required)
    if source_type == "brand_second":
        required_prov |= {"brand", "product_name", "model_sku"}
        if spec.perishable:
            err("source_type", "food cannot be listed as a brand second")
        if not data.get("new_price_per_unit"):
            err("new_price_per_unit", "brand seconds must state the original MRP")
    for key in sorted(required_prov):
        if not str(data.get(key) or "").strip():
            err(key, f"{PROVENANCE_FIELDS[key]} is required for {spec.label.lower()}")
    year = data.get("purchase_year")
    if year is not None and not (1980 <= int(year) <= now.year):
        err("purchase_year", f"must be between 1980 and {now.year}")

    # --- category attributes ---
    raw = dict(data.get("attributes") or {})
    clean: dict = {}
    allowed = expected_attributes(spec, source_type)
    for attr in allowed:
        value = raw.pop(attr.key, None)
        if value is None or value == "":
            if attr.required:
                err(f"attributes.{attr.key}", f"{attr.label} is required")
            continue
        try:
            clean[attr.key] = _coerce(attr, value)
        except (ValueError, TypeError) as e:
            err(f"attributes.{attr.key}", f"{attr.label} {e}")
    for unknown in raw:
        err(f"attributes.{unknown}", "is not a field for this category")

    # --- category-specific trust & safety rules ---
    if source_type == "brand_second" and clean.get("cosmetic_only") is False:
        err("attributes.cosmetic_only", "only cosmetic defects can be sold; safety or function defects cannot")

    if spec.key == "electronics" and clean.get("device_type") in DATA_BEARING_DEVICES \
            and route in ("resell", "donate") and clean.get("data_wiped") is not True:
        err("attributes.data_wiped", "wipe all data before reselling or donating a device that stores it")

    if spec.key == "clothing" and route == "donate" and clean.get("washed_clean") is not True:
        err("attributes.washed_clean", "donated clothes must be washed and clean")

    derived: dict = {}
    if spec.perishable:
        if data.get("asking_price_per_unit"):
            err("asking_price_per_unit", "food is always donated for free")
        cooked = clean.get("cooked_at")
        storage = clean.get("storage")
        if cooked and storage:
            cooked_dt = parse_dt(cooked)
            pickup_by = cooked_dt + timedelta(hours=FOOD_MAX_HOURS[storage])
            if cooked_dt > now + timedelta(minutes=5):
                err("attributes.cooked_at", "cannot be in the future")
            elif pickup_by <= now:
                err("attributes.cooked_at",
                    f"too old: {storage.replace('_', ' ')} food must be picked up within "
                    f"{FOOD_MAX_HOURS[storage]} hours of cooking")
            derived["pickup_by"] = pickup_by

    if route == "donate" and data.get("asking_price_per_unit"):
        err("asking_price_per_unit", "donations are free, so remove the price")

    # --- price ceiling: second-hand must be cheaper than new (recycling sells at scrap rates instead) ---
    price = data.get("asking_price_per_unit")
    if price and route == "resell" and not any(e["field"] == "unit" for e in errors):
        cap = valuation.price_cap_per_unit(spec, {**data, "attributes": clean})
        if cap is not None and price > cap:
            err("asking_price_per_unit",
                f"too high for a {data.get('condition', '').replace('_', ' ')} "
                f"{'brand second' if source_type == 'brand_second' else 'second-hand item'}: "
                f"the maximum is ₹{cap:,.0f} per {data.get('unit')}")

    return clean, derived, errors
