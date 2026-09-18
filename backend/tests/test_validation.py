from datetime import timedelta

from app.catalog import get_spec
from app.models import utcnow
from app.services.validation import validate_listing

TILES = dict(
    title="Matte white tiles", category="tiles", unit="pieces", quantity=40, condition="good", route="resell", source_type="business_surplus",
    reason_code="project_surplus", reason_detail="Left over after finishing a villa project.",
    brand="Terrano Tiles", model_sku="TR-6060-MW", manufacturer_color="Arctic Matte White",
    purchased_from="Kavya Tiles", asking_price_per_unit=95,
    attributes=dict(material="vitrified", size_mm="600x600", finish="matte", usage="floor", boxed=True),
)


def fields(spec_key, data):
    _, _, errors = validate_listing(get_spec(spec_key), data)
    return {e["field"] for e in errors}


def test_valid_tiles_pass():
    assert fields("tiles", TILES) == set()


def test_all_missing_basics_reported_together():
    errs = fields("tiles", {**TILES, "title": "", "quantity": None, "reason_detail": ""})
    assert {"title", "quantity", "reason_detail"} <= errs


def test_reason_for_disposal_is_required_and_meaningful():
    assert "reason_detail" in fields("tiles", {**TILES, "reason_detail": "leftover"})
    assert "reason_code" in fields("tiles", {**TILES, "reason_code": "because"})
    assert "reason_detail" in fields("tiles", {**TILES, "reason_code": "other", "reason_detail": "not needed anymore"})


def test_provenance_required_for_tiles():
    errs = fields("tiles", {**TILES, "manufacturer_color": "", "purchased_from": None})
    assert {"manufacturer_color", "purchased_from"} <= errs


def test_attribute_types_enums_and_unknown_keys():
    errs = fields("tiles", {**TILES, "attributes": {**TILES["attributes"], "finish": "sparkly", "vibes": "good"}})
    assert {"attributes.finish", "attributes.vibes"} <= errs


def test_second_hand_price_must_be_below_new():
    assert "asking_price_per_unit" in fields("tiles", {**TILES, "asking_price_per_unit": 150})


def test_brand_second_rules():
    hoodie = dict(
        title="Hoodies", category="clothing", unit="pieces", quantity=10, condition="new", route="resell", source_type="brand_second",
        reason_code="manufacturing_defect", reason_detail="Logo printed off-centre, failed QC.",
        brand="UrbanThread", product_name="Hoodie", model_sku="UT-1", new_price_per_unit=1299, asking_price_per_unit=349,
        attributes=dict(garment_type="hoodie", sizes="M", gender="unisex", washed_clean=True,
                        defect_type="stitching", defect_description="loose seam", cosmetic_only=False),
    )
    assert "attributes.cosmetic_only" in fields("clothing", hoodie)
    assert "asking_price_per_unit" in fields("clothing", {**hoodie, "asking_price_per_unit": 1000})  # cap is 70% of MRP
    assert "new_price_per_unit" in fields("clothing", {**hoodie, "new_price_per_unit": None})


def test_laptop_must_be_wiped_before_resale():
    laptop = dict(title="Laptop", category="electronics", unit="pieces", quantity=1, condition="good", route="resell",
                  reason_code="upgrade", reason_detail="Bought a new one for work.", brand="X", model_sku="Y",
                  asking_price_per_unit=10000, attributes=dict(device_type="laptop", working_status="fully_working"))
    assert "attributes.data_wiped" in fields("electronics", laptop)


def test_food_time_window():
    now = utcnow()
    food = dict(title="Dal rice", category="food_cooked", unit="plates", quantity=40, condition="new", route="donate",
                reason_code="end_of_day", reason_detail="Buffet surplus from lunch service.",
                attributes=dict(dish_name="Dal rice", diet="veg", storage="room_temp", packaging="covered_trays",
                                cooked_at=(now - timedelta(hours=1)).isoformat()))
    _, derived, errors = validate_listing(get_spec("food_cooked"), food)
    assert not errors and derived["pickup_by"] > now
    stale = {**food, "attributes": {**food["attributes"], "cooked_at": (now - timedelta(hours=5)).isoformat()}}
    assert "attributes.cooked_at" in fields("food_cooked", stale)
    assert "asking_price_per_unit" in fields("food_cooked", {**food, "asking_price_per_unit": 20})
