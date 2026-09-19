"""Rule-based valuation. Transparent estimates, not live market prices."""
from __future__ import annotations

from app.catalog import CategorySpec, factor

# Share of the new price a second-hand item is typically worth, by condition.
CONDITION_MULT = {"new": 0.80, "like_new": 0.65, "good": 0.50, "fair": 0.32, "poor": 0.15}
# The most a seller may ask, as a share of the new price.
CAP_MULT = {"new": 0.85, "like_new": 0.75, "good": 0.65, "fair": 0.45, "poor": 0.25}
BRAND_SECOND_CAP = 0.70
RANGE = 0.15

# Platform commission on resell / recycle, tiered by order value. Donations are free.
COMMISSION_TIERS = ((2_000, 0.10), (20_000, 0.08), (100_000, 0.06), (float("inf"), 0.05))
POOL_FLAT_FEE = 49.0


def new_price_per_unit(spec: CategorySpec, data: dict) -> float | None:
    return data.get("new_price_per_unit") or factor(spec, data.get("attributes") or {}, "new_price", data.get("unit"))


def weight_kg(spec: CategorySpec, data: dict) -> float:
    if data.get("weight_kg"):
        return float(data["weight_kg"])
    per_unit = factor(spec, data.get("attributes") or {}, "unit_weight_kg", data.get("unit")) or 1.0
    return float(data["quantity"]) * per_unit


def price_cap_per_unit(spec: CategorySpec, data: dict) -> float | None:
    new = new_price_per_unit(spec, data)
    if not new:
        return None
    if data.get("source_type") == "brand_second":
        return round(new * BRAND_SECOND_CAP, 2)
    return round(new * CAP_MULT.get(data.get("condition"), 0.5), 2)


def estimate(spec: CategorySpec, data: dict) -> dict:
    """Estimated recoverable value (INR) for the whole lot, on the chosen route."""
    route = data.get("route")
    qty = float(data["quantity"])
    attrs = data.get("attributes") or {}
    if route == "donate" or spec.perishable:
        return {"low": 0.0, "high": 0.0, "basis": "donated for free", "cap_per_unit": None}
    if route == "recycle":
        kg = weight_kg(spec, data)
        rate = factor(spec, attrs, "scrap_price_per_kg") or 0
        mid = kg * rate
        basis = f"{kg:,.0f} kg × ₹{rate:g}/kg scrap rate"
    else:
        new = new_price_per_unit(spec, data)
        if not new:
            return {"low": None, "high": None, "basis": "no reference price", "cap_per_unit": None}
        mult = BRAND_SECOND_CAP * 0.85 if data.get("source_type") == "brand_second" \
            else CONDITION_MULT.get(data.get("condition"), 0.5)
        mid = qty * new * mult
        basis = f"{qty:g} {data.get('unit')} × ₹{new:,.0f} new × {mult:.0%} for {data.get('condition')} condition"
    return {
        "low": round(mid * (1 - RANGE), -1),
        "high": round(mid * (1 + RANGE), -1),
        "basis": basis,
        "cap_per_unit": price_cap_per_unit(spec, data),
    }


def commission_rate(subtotal: float, route: str) -> float:
    if route == "donate":
        return 0.0
    return next(rate for limit, rate in COMMISSION_TIERS if subtotal < limit)


def commission(subtotal: float, route: str) -> float:
    return round(subtotal * commission_rate(subtotal, route), 2)


def pickup_fee(stops: int, total_km: float) -> float:
    """One consolidated pickup: a base fee, plus a charge per stop and per km."""
    return round(250 + 120 * max(stops - 1, 0) + 14 * total_km, 0)
