"""Recommends the best route for an item: reuse > resell > donate > recycle, within what's allowed."""
from __future__ import annotations

from app.catalog import CategorySpec


def recommend(spec: CategorySpec, data: dict) -> dict:
    attrs = data.get("attributes") or {}
    cond = data.get("condition")
    source = data.get("source_type")
    reasons: list[str] = []

    def pick(route: str, why: str) -> dict:
        reasons.append(why)
        alternatives = [r for r in spec.routes if r != route]
        return {"route": route, "why": reasons, "alternatives": alternatives, "reuse_ideas": list(spec.reuse_ideas)}

    if spec.perishable:
        return pick("donate", "Cooked food is only ever donated, for free, to verified NGOs.")
    if source == "brand_second":
        return pick("resell", "Factory seconds with cosmetic flaws are sold below MRP to people who can't afford full price.")
    if spec.key == "electronics" and attrs.get("working_status") == "not_working":
        return pick("recycle", "Devices that don't work go to a certified e-waste recycler so metals are recovered safely.")
    if spec.key == "other" and attrs.get("works_as_intended") is False:
        return pick("recycle", "It doesn't work as intended, so recovering the material is the best use.")
    if spec.key == "metal":
        return pick("recycle", "Metal scrap has a reliable recycling value, and recyclers pay by weight.")
    if cond == "poor" and "recycle" in spec.routes:
        return pick("recycle", "Poor condition makes resale unlikely; material recovery is the best use.")
    if spec.key in ("clothing", "furniture") and data.get("reason_code") in ("outgrown", "unused_gift", "relocation") \
            and cond in ("new", "like_new", "good") and "donate" in spec.routes and not data.get("asking_price_per_unit"):
        return pick("donate", "It's in good shape and you haven't set a price, so an NGO can put it to use today.")
    if "resell" in spec.routes and cond in ("new", "like_new", "good", "fair"):
        out = pick("resell", "It still has resale value, and a buyer nearby can use it as-is.")
        if spec.poolable:
            out["why"].append("It can also be pooled with other sellers' matching stock for bigger buyers.")
        return out
    if "reuse" in spec.routes:
        return pick("reuse", "Low resale value, but it's great for DIY reuse.")
    return pick(spec.routes[0], "Default route for this category.")
