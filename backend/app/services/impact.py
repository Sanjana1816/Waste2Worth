"""Impact score: rough CO2e avoided by keeping material in use instead of landfill."""
from __future__ import annotations

from app.catalog import CategorySpec, factor
from app.services.valuation import weight_kg

# Reuse avoids making a new product; recycling only avoids part of the virgin-material footprint.
ROUTE_CREDIT = {"reuse": 1.0, "resell": 1.0, "donate": 1.0, "recycle": 0.4}


def co2_saved_kg(spec: CategorySpec, data: dict, quantity: float | None = None) -> float:
    d = dict(data)
    if quantity is not None:
        d["quantity"] = quantity
        d["weight_kg"] = None if not data.get("weight_kg") else data["weight_kg"] * quantity / data["quantity"]
    kg = weight_kg(spec, d)
    per_kg = factor(spec, d.get("attributes") or {}, "co2_kg_per_kg") or 1.0
    return round(kg * per_kg * ROUTE_CREDIT.get(d.get("route"), 1.0), 1)


def meals(spec: CategorySpec, unit: str, quantity: float) -> int:
    if not spec.perishable:
        return 0
    return int(quantity / 0.3 if unit == "kg" else quantity)   # plates, packets, boxes ≈ one meal each
