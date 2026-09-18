"""Seed a realistic Bengaluru demo dataset.

    python -m scripts.seed            # adds data if the DB is empty
    python -m scripts.seed --reset    # wipes the DB and uploads first

Every listing goes through the real pipeline: validation -> synthetic photos -> quality and
colour checks -> publish. So this also works as an end-to-end smoke test.
All organisations are fictional.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
import uuid
from datetime import timedelta

from sqlmodel import Session, SQLModel, select

from app.catalog import get_spec
from app.db import engine, init_db
from app.models import Claim, Listing, ListingImage, ListingStatus, Org, OrgRole, utcnow
from app.schemas import PoolRequest
from app.services import dispatch, imaging, listings as svc, pooling, storage
from scripts.synth import COOL_SHADE, DAYLIGHT, WARM_BULB, photo

ORGS = [
    dict(name="BuildRight Contractors (Whitefield site)", role=OrgRole.business, lat=12.9698, lng=77.7500, verified=True),
    dict(name="Sharma Interiors", role=OrgRole.business, lat=12.9784, lng=77.6408, verified=True),
    dict(name="Kavya Tiles & Sanitary", role=OrgRole.business, lat=12.9116, lng=77.6474, verified=True),
    dict(name="Nimbus Tech Park Facilities", role=OrgRole.business, lat=12.9352, lng=77.6245, verified=True),
    dict(name="Spice Route Kitchen", role=OrgRole.business, lat=12.9340, lng=77.6260, verified=True),
    dict(name="UrbanThread Apparel", role=OrgRole.brand, lat=13.0280, lng=77.5190, verified=True, badges=["Brand verified"]),
    dict(name="Ravi Renovations", role=OrgRole.buyer, lat=12.9569, lng=77.7011, verified=True),
    dict(name="Anita K.", role=OrgRole.buyer, lat=12.9250, lng=77.6700),
    dict(name="Meera S.", role=OrgRole.individual, lat=12.9279, lng=77.6271),
    dict(name="CircuitCycle E-Waste Recyclers", role=OrgRole.recycler, lat=12.9900, lng=77.6600, verified=True,
         certified_recycler=True, accepts_categories=["electronics"], badges=["Certified e-waste recycler"]),
    dict(name="MetalMart Scrap Traders", role=OrgRole.recycler, lat=12.9600, lng=77.6400, verified=True,
         accepts_categories=["metal", "packaging", "wood"]),
    dict(name="Full Plate Foundation", role=OrgRole.ngo, lat=12.9380, lng=77.6200, verified=True,
         accepts_categories=["food_cooked", "clothing"], badges=["Verified NGO"]),
    dict(name="Second Serving Trust", role=OrgRole.ngo, lat=12.9450, lng=77.6350, verified=True,
         accepts_categories=["food_cooked"], badges=["Verified NGO"]),
    dict(name="Hope Kitchen Collective", role=OrgRole.ngo, lat=12.9300, lng=77.6100, verified=False,
         accepts_categories=["food_cooked"]),
    dict(name="ThreadShare", role=OrgRole.ngo, lat=12.9700, lng=77.6000, verified=True,
         accepts_categories=["clothing", "fabric", "furniture"], badges=["Verified NGO"]),
]

TILE = dict(category="tiles", unit="pieces", condition="good", brand="Terrano Tiles", product_name="Terrano Nordic",
            model_sku="TR-6060-MW", manufacturer_color="Arctic Matte White", purchased_from="Kavya Tiles & Sanitary, HSR",
            purchase_year=2025, has_invoice=True,
            attributes=dict(material="vitrified", size_mm="600x600", thickness_mm=9, finish="matte", usage="floor", boxed=True))


def L(seller: str, **kw) -> dict:
    return {"seller": seller, **kw}


def listings(now) -> list[dict]:
    ago = lambda m: (now - timedelta(minutes=m)).isoformat()  # noqa: E731
    return [
        L("BuildRight Contractors (Whitefield site)", **TILE, title="Terrano 600x600 matte white floor tiles", quantity=40,
          asking_price_per_unit=95, reason_code="project_surplus",
          reason_detail="Villa project finished; these 40 tiles were left over in sealed boxes.",
          _color=(232, 228, 220), _light=(DAYLIGHT, 1.0)),
        L("Sharma Interiors", **{**TILE, "attributes": {**TILE["attributes"], "batch_shade_code": "B24-117"}},
          title="Matte white vitrified tiles, 600x600", quantity=70, asking_price_per_unit=90,
          reason_code="design_change", reason_detail="Client switched to wooden flooring after we had bought the tiles.",
          _color=(230, 227, 219), _light=(WARM_BULB, 0.9)),
        L("Kavya Tiles & Sanitary", **{**TILE, "condition": "like_new"}, title="Terrano Arctic Matte White, dealer stock",
          quantity=90, asking_price_per_unit=100, reason_code="discontinued_stock",
          reason_detail="The design has been discontinued by the brand; clearing old showroom stock.",
          _color=(233, 229, 222), _light=(COOL_SHADE, 0.8)),
        L("Nimbus Tech Park Facilities", **TILE, title="White 600x600 tiles (older batch)", quantity=60,
          asking_price_per_unit=85, reason_code="renovation_removal",
          reason_detail="Spare tiles from the 2025 lobby job; the box says a different batch.",
          _color=(214, 204, 186), _light=(DAYLIGHT, 1.0)),
        L("Nimbus Tech Park Facilities", category="electronics", unit="pieces", condition="fair", quantity=12,
          title="Office laptops, i5 8th gen, 8 GB RAM", brand="Lenara", model_sku="ThinkLite T480", purchase_year=2019,
          asking_price_per_unit=9000, reason_code="office_refresh",
          reason_detail="IT refresh: replaced with new laptops. All drives wiped and tested.",
          attributes=dict(device_type="laptop", model_year=2018, working_status="fully_working",
                          specs="i5-8350U, 8 GB, 256 GB SSD", data_wiped=True, accessories="chargers"),
          _color=(40, 42, 48)),
        L("Nimbus Tech Park Facilities", category="electronics", unit="pieces", condition="poor", quantity=8,
          title="Dead 22-inch monitors", brand="Viewtek", model_sku="VT-22H", route="recycle",
          reason_code="broken", reason_detail="No display on power-up; repair quote was more than a new one.",
          attributes=dict(device_type="monitor", working_status="not_working"), _color=(30, 30, 32)),
        L("UrbanThread Apparel", category="clothing", source_type="brand_second", unit="pieces", condition="new",
          quantity=60, title="Oversized cotton hoodie, misprinted logo", brand="UrbanThread",
          product_name="Oversized Logo Hoodie", model_sku="UT-HD-221", manufacturer_color="Lilac Haze",
          new_price_per_unit=1299, asking_price_per_unit=349, reason_code="manufacturing_defect",
          reason_detail="Chest logo was printed 4 mm off-centre on this batch, so it failed QC.",
          attributes=dict(garment_type="hoodie", sizes="S x10, M x20, L x20, XL x10", gender="unisex",
                          fabric="100% cotton fleece", washed_clean=True, defect_type="print_misalignment",
                          defect_description="Logo shifted 4 mm to the left on the chest", cosmetic_only=True),
          _color=(165, 140, 230)),
        L("UrbanThread Apparel", category="fabric", unit="kg", condition="new", quantity=90,
          title="Cotton fleece off-cuts, mixed pastels", asking_price_per_unit=60, reason_code="offcuts",
          reason_detail="Cutting-room waste from the hoodie line. Clean and sorted by colour.",
          attributes=dict(fabric_type="cotton", piece_size="20-60 cm", colours="lilac, mint, cream", printed=False),
          _color=(190, 225, 205)),
        L("BuildRight Contractors (Whitefield site)", category="metal", unit="kg", condition="fair", quantity=350,
          title="TMT rebar off-cuts", route="recycle", asking_price_per_unit=32, reason_code="project_surplus",
          reason_detail="Off-cuts from column work, 0.5-2 m lengths, stacked at the site gate.",
          attributes=dict(metal="steel", form="rebar", rust_level="light"), _color=(110, 90, 80)),
        L("Nimbus Tech Park Facilities", category="furniture", unit="pieces", condition="good", quantity=25,
          title="Mesh-back office chairs", brand="Seatwell", asking_price_per_unit=900, reason_code="office_refresh",
          reason_detail="Floor 3 moved to hot-desking, so these chairs are surplus. All wheels work.",
          attributes=dict(item_type="chair", material="mixed", needs_repair=False), _color=(50, 55, 65)),
        L("Meera S.", category="clothing", unit="pieces", condition="good", quantity=15, route="donate",
          title="Kids' clothes, ages 4-7", brand="Assorted", reason_code="outgrown",
          reason_detail="My twins outgrew these. Everything is washed and folded.",
          attributes=dict(garment_type="kidswear", sizes="4-7 years", gender="kids", washed_clean=True),
          _color=(250, 180, 90)),
        L("Spice Route Kitchen", category="food_cooked", unit="plates", condition="new", quantity=40, route="donate",
          title="40 plates veg biryani", reason_code="cancelled_order",
          reason_detail="A corporate lunch order for 40 was cancelled at the last minute.",
          attributes=dict(dish_name="Veg biryani", diet="veg", cooked_at=ago(45), storage="hot_holding",
                          packaging="sealed_containers", allergens="contains dairy, cashew"),
          _color=(230, 160, 60), _dispatch=True),
        L("Spice Route Kitchen", category="food_cooked", unit="plates", condition="new", quantity=25, route="donate",
          title="25 plates dal rice", reason_code="end_of_day",
          reason_detail="End-of-day surplus from the lunch buffet, kept in a hot case.",
          attributes=dict(dish_name="Dal rice", diet="veg", cooked_at=ago(90), storage="hot_holding",
                          packaging="covered_trays"),
          _color=(220, 190, 90), _claim_by="Full Plate Foundation"),
    ]


def reset() -> None:
    SQLModel.metadata.drop_all(engine)
    storage.clear_local()


def _store(session: Session, li: Listing, shot_key: str, data: bytes) -> None:
    img = imaging.open_image(data)
    result = imaging.analyze(img, shot_key)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    key = storage.save(f"{li.id}/{shot_key}_{uuid.uuid4().hex[:10]}.jpg", buf.getvalue())
    session.add(ListingImage(listing_id=li.id, shot_type=shot_key, path=key, **result))


def add_photos(session: Session, spec, li: Listing, color, light) -> None:
    tint, exposure = light
    required = svc.required_shots(spec, li)
    for i, shot in enumerate(required):
        _store(session, li, shot.key, photo(color, tint=tint, exposure=exposure, seed=li.id * 10 + i))
    # top up to the minimum count with optional shots
    extra = [s for s in spec.shots if not s.required and s not in required]
    for j, shot in enumerate(extra[: max(0, spec.min_images - len(required))]):
        _store(session, li, shot.key, photo(color, tint=tint, exposure=exposure, seed=li.id * 10 + 9 - j))
    session.commit()


def run(do_reset: bool = False) -> None:
    if do_reset:
        reset()
    init_db()
    with Session(engine) as session:
        if session.exec(select(Org)).first():
            print("Database already has data. Use --reset to start over.")
            return
        orgs = {}
        demo_phone = os.environ.get("DEMO_NGO_PHONE")  # your own number, to receive the NGO call on stage
        for o in ORGS:
            org = Org(**o)
            if demo_phone and o["name"] == "Full Plate Foundation":
                org.phone = demo_phone
            session.add(org)
            orgs[o["name"]] = org
        session.commit()

        now = utcnow()
        for raw in listings(now):
            raw = dict(raw)
            seller = orgs[raw.pop("seller")]
            color, light = raw.pop("_color"), raw.pop("_light", (DAYLIGHT, 1.0))
            do_dispatch, claim_by = raw.pop("_dispatch", False), raw.pop("_claim_by", None)
            spec = get_spec(raw["category"])
            li = Listing(**raw, seller_id=seller.id, lat=seller.lat, lng=seller.lng, quantity_available=raw["quantity"],
                         ai_summary={"demo_photos": True})  # synthetic photos: the UI shows illustrations on cards
            svc.validate_and_enrich(spec, li)
            session.add(li)
            session.commit()
            session.refresh(li)
            add_photos(session, spec, li, color, light)
            state = svc.publish(session, spec, li)
            if not state["ready"]:
                raise SystemExit(f"seed listing '{li.title}' not publishable: {state}")
            tag = f" colour {li.measured_color_hex}" if li.measured_color_hex else ""
            print(f"  published #{li.id:<3} {li.route:<8} {li.title}{tag}")
            if do_dispatch:
                for log in asyncio.run(dispatch.dispatch_food(session, li)):
                    print(f"      dispatch {log.channel}: {log.status}")
            if claim_by:
                ngo = orgs[claim_by]
                li.quantity_available, li.status = 0, ListingStatus.claimed
                session.add_all([li, Claim(listing_id=li.id, org_id=ngo.id, quantity=li.quantity,
                                           status="picked_up", picked_up_at=utcnow())])
                session.commit()
                print(f"      claimed and picked up by {ngo.name}")
        # A couple of completed orders so the impact numbers aren't empty.
        by_title = {li.title: li for li in session.exec(select(Listing)).all()}
        for buyer, title, qty in (("Ravi Renovations", "Mesh-back office chairs", 10),
                                  ("MetalMart Scrap Traders", "TMT rebar off-cuts", 350)):
            req = PoolRequest(buyer_id=orgs[buyer].id, listing_id=by_title[title].id, quantity=qty)
            pool = pooling.confirm(session, pooling.reserve(session, req))
            print(f"  order #{pool.id}: {buyer} bought {qty:g} of '{title}' for Rs {pool.total:,.0f}")
        print(f"Seeded {len(ORGS)} organisations.")


if __name__ == "__main__":
    run("--reset" in sys.argv)
