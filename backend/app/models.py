from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class OrgRole(str, Enum):
    business = "business"      # generates waste (builder, restaurant, office...)
    brand = "brand"            # sells factory seconds
    buyer = "buyer"
    recycler = "recycler"
    ngo = "ngo"
    individual = "individual"


class ListingStatus(str, Enum):
    draft = "draft"
    published = "published"
    sold_out = "sold_out"
    claimed = "claimed"
    expired = "expired"
    withdrawn = "withdrawn"


class Org(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    role: OrgRole
    phone: str | None = None
    city: str = "Bengaluru"
    lat: float
    lng: float
    verified: bool = False
    certified_recycler: bool = False
    badges: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    accepts_categories: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class Listing(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    seller_id: int = Field(foreign_key="org.id", index=True)
    category: str = Field(index=True)
    source_type: str = "business_surplus"
    route: str = Field(index=True)
    title: str
    description: str = ""

    quantity: float
    unit: str
    quantity_available: float
    quantity_reserved: float = 0
    weight_kg: float | None = None
    condition: str

    # why the seller considers this waste
    reason_code: str
    reason_detail: str

    # provenance
    brand: str | None = None
    product_name: str | None = None
    model_sku: str | None = None
    manufacturer_color: str | None = None
    purchased_from: str | None = None
    purchase_year: int | None = None
    has_invoice: bool = False

    attributes: dict = Field(default_factory=dict, sa_column=Column(JSON))

    asking_price_per_unit: float | None = None
    new_price_per_unit: float | None = None    # MRP / price when new (seller-supplied)
    est_value_low: float | None = None
    est_value_high: float | None = None
    price_cap_per_unit: float | None = None
    co2_saved_kg: float | None = None

    measured_color_hex: str | None = None
    measured_color_lab: list[float] | None = Field(default=None, sa_column=Column(JSON))

    lat: float
    lng: float
    pickup_by: datetime | None = None

    ai_summary: dict | None = Field(default=None, sa_column=Column(JSON))
    route_suggestion: dict | None = Field(default=None, sa_column=Column(JSON))
    status: ListingStatus = Field(default=ListingStatus.draft, index=True)
    vakh_post_id: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    published_at: datetime | None = None


class ListingImage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    shot_type: str
    path: str
    width: int
    height: int
    blur_score: float
    brightness: float
    quality_ok: bool
    issues: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    color_hex: str | None = None
    color_lab: list[float] | None = Field(default=None, sa_column=Column(JSON))
    white_balanced: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Pool(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    buyer_id: int = Field(foreign_key="org.id")
    category: str
    pool_key: str
    quantity: float
    unit: str
    subtotal: float
    pickup_fee: float
    platform_fee: float
    total: float
    new_price_total: float | None
    savings_pct: float | None
    shade_match_pct: float | None
    # reserved -> confirmed -> out_for_pickup -> delivered (or cancelled / expired)
    status: str = "reserved"
    reserved_until: datetime
    created_at: datetime = Field(default_factory=utcnow)
    confirmed_at: datetime | None = None
    delivered_at: datetime | None = None


class PoolItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    pool_id: int = Field(foreign_key="pool.id", index=True)
    listing_id: int = Field(foreign_key="listing.id")
    quantity: float
    unit_price: float
    line_total: float
    distance_km: float
    delta_e: float | None = None
    picked_up_at: datetime | None = None    # this seller's lot collected by the driver


class Claim(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    org_id: int = Field(foreign_key="org.id")
    quantity: float
    status: str = "claimed"    # claimed | picked_up | cancelled
    created_at: datetime = Field(default_factory=utcnow)
    picked_up_at: datetime | None = None


class DispatchLog(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="listing.id", index=True)
    org_id: int | None = Field(default=None, foreign_key="org.id")
    channel: str               # voice_call | vakh
    status: str                # sent | simulated | failed
    detail: str = ""
    created_at: datetime = Field(default_factory=utcnow)
