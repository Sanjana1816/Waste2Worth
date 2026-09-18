"""Category catalogue: the single source of truth for what each kind of waste needs.

Every category declares
  - the product-specific attributes a seller must fill in,
  - which provenance fields (brand, SKU, manufacturer colour, ...) are mandatory,
  - the photo shots required (and the minimum photo count),
  - the allowed "why is this waste?" reasons,
  - reference numbers used by valuation and impact scoring.

The frontend renders its listing form from GET /api/categories/{key}, so adding a
category here is enough to support it end to end.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Literal

AttrType = Literal["text", "int", "number", "enum", "bool", "datetime"]
Route = Literal["reuse", "recycle", "resell", "donate"]

ROUTES: tuple[Route, ...] = ("reuse", "recycle", "resell", "donate")
CONDITIONS = ("new", "like_new", "good", "fair", "poor")
SOURCE_TYPES = ("business_surplus", "brand_second", "individual")

# Provenance fields live as columns on Listing (not in `attributes`) because
# pooling, search and trust checks rely on them across every category.
PROVENANCE_FIELDS = {
    "brand": "Brand / manufacturer",
    "product_name": "Product name as sold",
    "model_sku": "Model number / SKU / design code",
    "manufacturer_color": "Colour name exactly as the company describes it",
    "purchased_from": "Where it was bought (dealer, store, website)",
    "purchase_year": "Year of purchase",
}


@dataclass(frozen=True)
class Attr:
    key: str
    label: str
    type: AttrType
    required: bool = True
    options: tuple[str, ...] = ()
    unit: str | None = None
    help: str | None = None


@dataclass(frozen=True)
class Shot:
    key: str
    label: str
    help: str
    required: bool = True


@dataclass(frozen=True)
class Reason:
    key: str
    label: str


@dataclass(frozen=True)
class CategorySpec:
    key: str
    label: str
    group: str
    routes: tuple[Route, ...]
    units: tuple[str, ...]
    attributes: tuple[Attr, ...]
    shots: tuple[Shot, ...]
    min_images: int
    reasons: tuple[Reason, ...]
    provenance_required: tuple[str, ...] = ()
    # valuation references (INR). `new_price` is per unit; `by_option` lets one
    # attribute (e.g. device_type) override price / weight / co2 factors.
    new_price: dict[str, float] = field(default_factory=dict)
    unit_weight_kg: dict[str, float] = field(default_factory=dict)
    scrap_price_per_kg: float = 0.0
    co2_kg_per_kg: float = 1.0
    option_attr: str | None = None
    by_option: dict[str, dict[str, float]] = field(default_factory=dict)
    # pooling: listings may be combined only when all these keys match
    poolable: bool = False
    pool_keys: tuple[str, ...] = ()
    color_critical: bool = False
    perishable: bool = False
    reuse_ideas: tuple[str, ...] = ()

    def shot(self, key: str) -> Shot | None:
        return next((s for s in self.shots if s.key == key), None)

    def attr(self, key: str) -> Attr | None:
        return next((a for a in self.attributes if a.key == key), None)

    def to_public(self) -> dict:
        d = asdict(self)
        d["provenance_required"] = [
            {"key": k, "label": PROVENANCE_FIELDS[k]} for k in self.provenance_required
        ]
        return d


COLOR_REFERENCE_SHOT = Shot(
    "color_reference",
    "Colour reference photo",
    "Place one item in the middle of a plain white A4 sheet and fill the frame so paper shows all "
    "around it. Shoot in daylight with the flash off. We use the white paper to cancel out your "
    "lighting so buyers see the true colour.",
)

BRAND_SECOND_ATTRS: tuple[Attr, ...] = (
    Attr("defect_type", "Type of defect", "enum", options=(
        "print_misalignment", "packaging_damage", "surface_scratch", "dent",
        "colour_variation", "stitching", "glaze_spot", "other")),
    Attr("defect_description", "Describe the defect and where it is", "text"),
    Attr("cosmetic_only", "The defect is cosmetic only and does not affect safety or function", "bool"),
)
DEFECT_SHOT = Shot("defect_closeup", "Defect close-up", "A sharp close-up of the flaw.")


def _reasons(*pairs: tuple[str, str]) -> tuple[Reason, ...]:
    return tuple(Reason(k, v) for k, v in pairs) + (Reason("other", "Other (explain below)"),)


CATEGORIES: dict[str, CategorySpec] = {}


def _register(spec: CategorySpec) -> None:
    CATEGORIES[spec.key] = spec


_register(CategorySpec(
    key="tiles", label="Tiles", group="Construction & demolition",
    routes=("reuse", "resell", "recycle"),
    units=("pieces", "sqft", "boxes", "kg"),
    attributes=(
        Attr("material", "Tile material", "enum", options=("ceramic", "vitrified", "porcelain", "natural_stone", "mosaic")),
        Attr("size_mm", "Tile size (mm)", "text", help="e.g. 600x600"),
        Attr("thickness_mm", "Thickness", "number", unit="mm", required=False),
        Attr("finish", "Surface finish", "enum", options=("matte", "glossy", "satin", "textured", "rustic")),
        Attr("usage", "Made for", "enum", options=("floor", "wall", "both")),
        Attr("batch_shade_code", "Batch / shade code printed on the box", "text", required=False,
             help="Tiles from different batches can differ in shade. The code is usually on the box."),
        Attr("boxed", "Still in original boxes", "bool"),
    ),
    shots=(
        Shot("full_lot", "Whole lot", "All the tiles stacked so the quantity is visible."),
        Shot("surface_closeup", "Surface close-up", "One tile face, filling the frame, in daylight."),
        Shot("label", "Box / label", "The label showing brand, design code and batch/shade code."),
        COLOR_REFERENCE_SHOT,
        Shot("edges", "Edges and corners", "Show any chips or cracks.", required=False),
    ),
    min_images=4,
    reasons=_reasons(("project_surplus", "Left over after a project"), ("over_ordered", "Ordered too many"),
                     ("design_change", "Design changed"), ("discontinued_stock", "Discontinued design (dealer stock)"),
                     ("renovation_removal", "Removed during renovation"), ("damaged_in_transit", "Some damaged in transit")),
    provenance_required=("brand", "model_sku", "manufacturer_color", "purchased_from"),
    new_price={"pieces": 160, "sqft": 55, "boxes": 640, "kg": 18},
    unit_weight_kg={"pieces": 8.5, "sqft": 2.2, "boxes": 34, "kg": 1},
    scrap_price_per_kg=0.5, co2_kg_per_kg=0.7,
    poolable=True, pool_keys=("brand", "model_sku", "manufacturer_color", "size_mm", "finish"),
    color_critical=True,
    reuse_ideas=("Mosaic garden path from broken pieces", "Tiled planter boxes", "Coasters and trivets",
                 "Kitchen or bathroom splash-back patch", "Pet feeding mat"),
))

_register(CategorySpec(
    key="wood", label="Wood & timber", group="Construction & demolition",
    routes=("reuse", "resell", "recycle"),
    units=("kg", "pieces", "sheets"),
    attributes=(
        Attr("wood_type", "Wood type", "enum", options=("plywood", "mdf", "solid_hardwood", "softwood", "particle_board", "laminate_board")),
        Attr("dimensions", "Typical piece size (L x W)", "text", help="e.g. 8ft x 4ft, or 'mixed off-cuts'"),
        Attr("thickness_mm", "Thickness", "number", unit="mm", required=False),
        Attr("treated_or_painted", "Treated, painted or laminated", "bool"),
        Attr("has_nails", "Has nails or screws in it", "bool"),
    ),
    shots=(
        Shot("full_lot", "Whole lot", "Everything in one frame."),
        Shot("closeup", "Close-up", "Grain and surface condition."),
        Shot("measure", "With measuring tape", "A tape across one piece so buyers see the size."),
    ),
    min_images=3,
    reasons=_reasons(("project_surplus", "Left over after a project"), ("demolition", "From demolition"),
                     ("offcuts", "Workshop off-cuts"), ("water_damage", "Minor water damage")),
    new_price={"kg": 45, "pieces": 400, "sheets": 1800},
    unit_weight_kg={"kg": 1, "pieces": 6, "sheets": 22},
    scrap_price_per_kg=4, co2_kg_per_kg=0.5,
    reuse_ideas=("Pallet-style shelf", "Raised garden bed", "Plant stand", "Wall-mounted key holder"),
))

_register(CategorySpec(
    key="metal", label="Metal scrap", group="Construction & demolition",
    routes=("recycle", "resell"),
    units=("kg",),
    attributes=(
        Attr("metal", "Metal", "enum", options=("steel", "iron", "stainless_steel", "aluminium", "copper", "brass", "mixed")),
        Attr("form", "Form", "enum", options=("rebar", "sheet", "pipe", "wire", "profile", "mixed")),
        Attr("rust_level", "Rust", "enum", options=("none", "light", "heavy")),
    ),
    shots=(
        Shot("full_lot", "Whole lot", "Everything in one frame."),
        Shot("closeup", "Close-up", "Surface and rust."),
    ),
    min_images=2,
    reasons=_reasons(("project_surplus", "Left over after a project"), ("demolition", "From demolition"),
                     ("machine_scrap", "Old machinery parts")),
    new_price={"kg": 70}, unit_weight_kg={"kg": 1},
    scrap_price_per_kg=30, co2_kg_per_kg=1.8,
    option_attr="metal",
    by_option={
        "aluminium": {"scrap_price_per_kg": 130, "co2_kg_per_kg": 9.0, "new_price": 250},
        "copper": {"scrap_price_per_kg": 650, "co2_kg_per_kg": 3.5, "new_price": 850},
        "brass": {"scrap_price_per_kg": 420, "co2_kg_per_kg": 3.0, "new_price": 600},
        "stainless_steel": {"scrap_price_per_kg": 55, "co2_kg_per_kg": 3.0, "new_price": 180},
    },
    reuse_ideas=("Garden trellis from rebar", "Industrial-style shelf brackets", "Sculpture / art pieces"),
))

_register(CategorySpec(
    key="fabric", label="Fabric off-cuts", group="Textiles",
    routes=("reuse", "resell", "recycle", "donate"),
    units=("kg", "meters"),
    attributes=(
        Attr("fabric_type", "Fabric", "enum", options=("cotton", "polyester", "denim", "silk", "wool", "linen", "blend")),
        Attr("piece_size", "Typical piece size", "text", help="e.g. 30-60 cm strips"),
        Attr("colours", "Main colours", "text"),
        Attr("printed", "Printed / patterned", "bool"),
    ),
    shots=(
        Shot("full_lot", "Whole lot", "The whole bundle."),
        Shot("texture_closeup", "Texture close-up", "Weave and print."),
        COLOR_REFERENCE_SHOT,
    ),
    min_images=3,
    reasons=_reasons(("offcuts", "Cutting-room off-cuts"), ("dead_stock", "Unsold rolls / dead stock"),
                     ("colour_rejected", "Rejected shade by buyer")),
    new_price={"kg": 320, "meters": 120}, unit_weight_kg={"kg": 1, "meters": 0.25},
    scrap_price_per_kg=12, co2_kg_per_kg=6.0,
    reuse_ideas=("Tote bags", "Patchwork quilt", "Rag rug", "Scrunchies and hair ties", "Cushion covers"),
))

_register(CategorySpec(
    key="clothing", label="Clothing", group="Textiles",
    routes=("resell", "donate", "recycle", "reuse"),
    units=("pieces", "kg"),
    attributes=(
        Attr("garment_type", "Garment", "enum", options=("tshirt", "shirt", "hoodie", "jeans", "dress", "saree", "kurta", "jacket", "kidswear", "other")),
        Attr("sizes", "Sizes available", "text", help="e.g. S x10, M x20"),
        Attr("gender", "For", "enum", options=("men", "women", "unisex", "kids")),
        Attr("fabric", "Fabric", "text", required=False),
        Attr("washed_clean", "Washed and clean", "bool"),
    ),
    shots=(
        Shot("front", "Front", "Laid flat, front side."),
        Shot("back", "Back", "Laid flat, back side."),
        Shot("label", "Brand / size tag", "Tag with brand, size and fabric."),
        COLOR_REFERENCE_SHOT,
    ),
    min_images=3,
    reasons=_reasons(("outgrown", "Outgrown / doesn't fit"), ("unused_gift", "Unused gift"),
                     ("style_change", "No longer my style"), ("overstock", "Shop overstock"),
                     ("manufacturing_defect", "Factory defect"), ("customer_return", "Customer return")),
    provenance_required=("brand",),
    new_price={"pieces": 700, "kg": 1400}, unit_weight_kg={"pieces": 0.4, "kg": 1},
    scrap_price_per_kg=8, co2_kg_per_kg=15.0,
    reuse_ideas=("Cropped / upcycled fit", "Cushion cover", "Cleaning rags", "Kids' clothes from adult sizes"),
))

_register(CategorySpec(
    key="electronics", label="Electronics & IT", group="E-waste",
    routes=("resell", "recycle", "donate"),
    units=("pieces",),
    attributes=(
        Attr("device_type", "Device", "enum", options=("laptop", "desktop", "monitor", "phone", "tablet", "printer", "networking", "small_appliance", "other")),
        Attr("model_year", "Year of manufacture", "int", required=False),
        Attr("working_status", "Working status", "enum", options=("fully_working", "partially_working", "not_working")),
        Attr("specs", "Key specs", "text", required=False, help="e.g. i5 8th gen, 8 GB RAM, 256 GB SSD"),
        Attr("data_wiped", "Personal / company data wiped", "bool", required=False),
        Attr("accessories", "Included accessories", "text", required=False, help="charger, cables, box..."),
    ),
    shots=(
        Shot("front", "Front", "Whole device, front."),
        Shot("back_ports", "Back / ports", "Back side and ports."),
        Shot("model_label", "Model label", "The sticker with model and serial (hide the serial if you like)."),
        Shot("powered_on", "Powered on", "Screen switched on. Skip if not working.", required=False),
    ),
    min_images=3,
    reasons=_reasons(("upgrade", "Replaced by a newer device"), ("end_of_life", "End of life / too slow"),
                     ("broken", "Broken, repair not worth it"), ("office_refresh", "Office IT refresh"),
                     ("manufacturing_defect", "Factory defect"), ("customer_return", "Customer return")),
    provenance_required=("brand", "model_sku"),
    new_price={"pieces": 15000}, unit_weight_kg={"pieces": 2},
    scrap_price_per_kg=40, co2_kg_per_kg=60.0,
    option_attr="device_type",
    by_option={
        "laptop": {"new_price": 45000, "unit_weight_kg": 2.0},
        "desktop": {"new_price": 38000, "unit_weight_kg": 8.0, "co2_kg_per_kg": 40.0},
        "monitor": {"new_price": 9000, "unit_weight_kg": 4.0, "co2_kg_per_kg": 45.0},
        "phone": {"new_price": 18000, "unit_weight_kg": 0.2, "co2_kg_per_kg": 300.0},
        "tablet": {"new_price": 20000, "unit_weight_kg": 0.5, "co2_kg_per_kg": 200.0},
        "printer": {"new_price": 12000, "unit_weight_kg": 6.0, "co2_kg_per_kg": 20.0},
        "small_appliance": {"new_price": 3500, "unit_weight_kg": 2.0, "co2_kg_per_kg": 10.0},
    },
    reuse_ideas=("Refurbish for a school computer lab", "Home media server", "Harvest RAM / SSD as spares",
                 "Old phone as a CCTV or baby monitor"),
))

_register(CategorySpec(
    key="furniture", label="Furniture", group="Institutions & offices",
    routes=("resell", "donate", "reuse", "recycle"),
    units=("pieces",),
    attributes=(
        Attr("item_type", "Item", "enum", options=("chair", "table", "desk", "cabinet", "shelf", "sofa", "bed", "bench", "other")),
        Attr("material", "Main material", "enum", options=("wood", "metal", "plastic", "upholstered", "mixed")),
        Attr("dimensions_cm", "Dimensions (W x D x H cm)", "text", required=False),
        Attr("needs_repair", "Needs repair", "bool"),
    ),
    shots=(
        Shot("front", "Front", "Whole item, front."),
        Shot("side", "Side", "Whole item, side."),
        Shot("wear_closeup", "Wear / damage close-up", "Scratches, stains, broken parts.", required=False),
        replace(COLOR_REFERENCE_SHOT, required=False),
    ),
    min_images=3,
    reasons=_reasons(("office_refresh", "Office / campus refurbishment"), ("relocation", "Moving out"),
                     ("upgrade", "Replaced with new"), ("business_closure", "Business closing")),
    new_price={"pieces": 6000}, unit_weight_kg={"pieces": 15},
    scrap_price_per_kg=5, co2_kg_per_kg=1.5,
    option_attr="item_type",
    by_option={"chair": {"new_price": 3500, "unit_weight_kg": 7}, "sofa": {"new_price": 25000, "unit_weight_kg": 40},
               "bed": {"new_price": 18000, "unit_weight_kg": 45}, "bench": {"new_price": 5000, "unit_weight_kg": 20}},
    reuse_ideas=("Re-upholster with fabric off-cuts", "Paint and stencil makeover", "Convert desk into a potting bench"),
))

_register(CategorySpec(
    key="packaging", label="Packaging material", group="Retail & warehouses",
    routes=("reuse", "resell", "recycle"),
    units=("kg", "pieces"),
    attributes=(
        Attr("material", "Material", "enum", options=("cardboard", "plastic_film", "bubble_wrap", "thermocol", "wooden_pallet", "plastic_crate", "mixed")),
        Attr("clean_dry", "Clean and dry", "bool"),
        Attr("size", "Box / pallet size", "text", required=False),
    ),
    shots=(
        Shot("full_lot", "Whole lot", "Everything in one frame."),
        Shot("closeup", "Close-up", "Condition of the material."),
    ),
    min_images=2,
    reasons=_reasons(("inbound_packaging", "Came with deliveries"), ("excess_stock", "Excess packaging stock"),
                     ("damaged_goods", "From damaged goods")),
    new_price={"kg": 60, "pieces": 90}, unit_weight_kg={"kg": 1, "pieces": 0.8},
    scrap_price_per_kg=9, co2_kg_per_kg=1.1,
    reuse_ideas=("Moving boxes for students", "Seedling trays", "Kids' craft kits", "Pallet furniture"),
))

_register(CategorySpec(
    key="food_cooked", label="Cooked food (surplus)", group="Food",
    routes=("donate",),
    units=("plates", "kg"),
    attributes=(
        Attr("dish_name", "Dish", "text"),
        Attr("diet", "Type", "enum", options=("veg", "non_veg", "egg", "vegan", "jain")),
        Attr("cooked_at", "Cooked at", "datetime"),
        Attr("storage", "How it is kept now", "enum", options=("hot_holding", "refrigerated", "room_temp")),
        Attr("packaging", "Packed in", "enum", options=("sealed_containers", "covered_trays", "bulk_vessel")),
        Attr("allergens", "Allergens (nuts, dairy, gluten...)", "text", required=False),
    ),
    shots=(
        Shot("food", "Food", "The food itself, clearly visible."),
        Shot("packaging", "Packaging", "How it is packed / covered."),
    ),
    min_images=2,
    reasons=_reasons(("end_of_day", "End-of-day surplus"), ("event_leftover", "Event / wedding leftover"),
                     ("overproduction", "Cooked too much"), ("cancelled_order", "Cancelled bulk order")),
    unit_weight_kg={"plates": 0.3, "kg": 1},
    co2_kg_per_kg=2.5,
    perishable=True,
))

# Hours a cooked-food listing stays claimable after cooking, by storage mode.
FOOD_MAX_HOURS = {"hot_holding": 4, "room_temp": 4, "refrigerated": 24}
DATA_BEARING_DEVICES = {"laptop", "desktop", "phone", "tablet"}


def get_spec(key: str) -> CategorySpec | None:
    return CATEGORIES.get(key)


def factor(spec: CategorySpec, attrs: dict, name: str, unit: str | None = None) -> float | None:
    """Look up a valuation/impact factor, honouring per-option overrides."""
    opt = attrs.get(spec.option_attr) if spec.option_attr else None
    override = spec.by_option.get(opt or "", {})
    if name in override:
        val = override[name]
        # by_option values are per the category's primary unit; scale to the listing unit
        if unit and name in ("new_price", "unit_weight_kg"):
            base = getattr(spec, name).get(spec.units[0]) or 1
            return val * (getattr(spec, name).get(unit, base) / base)
        return val
    if name in ("new_price", "unit_weight_kg"):
        return getattr(spec, name).get(unit or spec.units[0])
    return getattr(spec, name)
