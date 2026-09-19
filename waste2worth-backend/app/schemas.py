from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models import OrgRole

Route = Literal["reuse", "recycle", "resell", "donate"]
Condition = Literal["new", "like_new", "good", "fair", "poor"]
SourceType = Literal["business_surplus", "brand_second", "individual"]


class OrgCreate(BaseModel):
    name: str = Field(min_length=2)
    role: OrgRole
    phone: str | None = None
    city: str = "Bengaluru"
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accepts_categories: list[str] = []


class ListingBase(BaseModel):
    source_type: SourceType = "business_surplus"
    route: Route | None = None
    title: str = Field(min_length=4, max_length=120)
    description: str = Field(default="", max_length=2000)
    quantity: float = Field(gt=0)
    unit: str
    weight_kg: float | None = Field(default=None, gt=0)
    condition: Condition
    reason_code: str
    reason_detail: str = Field(max_length=1000)
    brand: str | None = None
    product_name: str | None = None
    model_sku: str | None = None
    manufacturer_color: str | None = None
    purchased_from: str | None = None
    purchase_year: int | None = None
    has_invoice: bool = False
    attributes: dict = {}
    asking_price_per_unit: float | None = Field(default=None, ge=0)
    new_price_per_unit: float | None = Field(default=None, gt=0)
    lat: float | None = None
    lng: float | None = None


class ListingCreate(ListingBase):
    seller_id: int
    category: str


class ListingUpdate(BaseModel):
    """Partial update; any field of ListingBase may be sent."""
    model_config = {"extra": "forbid"}
    source_type: SourceType | None = None
    route: Route | None = None
    title: str | None = Field(default=None, min_length=4, max_length=120)
    description: str | None = None
    quantity: float | None = Field(default=None, gt=0)
    unit: str | None = None
    weight_kg: float | None = None
    condition: Condition | None = None
    reason_code: str | None = None
    reason_detail: str | None = None
    brand: str | None = None
    product_name: str | None = None
    model_sku: str | None = None
    manufacturer_color: str | None = None
    purchased_from: str | None = None
    purchase_year: int | None = None
    has_invoice: bool | None = None
    attributes: dict | None = None
    asking_price_per_unit: float | None = None
    new_price_per_unit: float | None = None


class PoolRequest(BaseModel):
    buyer_id: int
    quantity: float = Field(gt=0)
    # Either "I want more of this listing" ...
    listing_id: int | None = None
    # ... or a demand-first spec: category + the pool keys (brand, model_sku, ...)
    category: str | None = None
    match: dict[str, str] = {}
    unit: str | None = None
    radius_km: float | None = None


class ClaimRequest(BaseModel):
    org_id: int
    quantity: float | None = Field(default=None, gt=0)


class FieldError(BaseModel):
    field: str
    message: str


class ImageResult(BaseModel):
    id: int
    shot_type: str
    quality_ok: bool
    issues: list[str]
    blur_score: float
    brightness: float
    width: int
    height: int
    color_hex: str | None
    white_balanced: bool


class Readiness(BaseModel):
    ready: bool
    missing_shots: list[dict]
    retake_shots: list[dict]
    image_count: int
    min_images: int
    field_errors: list[FieldError]


class SpeakRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1500)
    voice_id: str | None = None


class TimeWindow(BaseModel):
    cooked_at: datetime
    pickup_by: datetime
