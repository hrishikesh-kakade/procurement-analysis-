from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import QuotationStatus, RfqStatus
from app.schemas.common import Money


class RfqItemCreate(BaseModel):
    material_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class RfqCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    requisition_id: int | None = Field(
        default=None, gt=0, description="Approved requisition to source (items are copied from it)"
    )
    due_date: date | None = None
    items: list[RfqItemCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_items(self) -> "RfqCreate":
        if not self.items and self.requisition_id is None:
            raise ValueError("items are required when requisition_id is not provided")
        ids = [i.material_id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate material_id in items")
        return self


class RfqItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    quantity: int


class RfqRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_number: str
    title: str
    description: str | None
    requisition_id: int | None
    status: RfqStatus
    due_date: date | None
    awarded_po_id: int | None
    items: list[RfqItemRead]
    created_at: datetime
    updated_at: datetime


class QuotationItemCreate(BaseModel):
    rfq_item_id: int = Field(gt=0)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class QuotationCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    supplier_id: int = Field(gt=0)
    delivery_days: int = Field(ge=0, le=365)
    notes: str | None = Field(default=None, max_length=2000)
    items: list[QuotationItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def _no_duplicates(self) -> "QuotationCreate":
        ids = [i.rfq_item_id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate rfq_item_id in items")
        return self


class QuotationItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_item_id: int
    unit_price: Money
    line_total: Money


class QuotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_id: int
    supplier_id: int
    status: QuotationStatus
    delivery_days: int
    total_amount: Money
    notes: str | None
    items: list[QuotationItemRead]
    created_at: datetime


class RfqAward(BaseModel):
    quotation_id: int = Field(gt=0)


class ComparisonRow(BaseModel):
    rank: int
    quotation_id: int
    supplier_id: int
    supplier_name: str
    status: QuotationStatus
    total_amount: Money
    delivery_days: int
    supplier_score: float | None
    price_points: float
    delivery_points: float
    supplier_points: float
    composite_score: float


class RfqComparison(BaseModel):
    rfq_id: int
    recommended_quotation_id: int | None
    weights: dict[str, int]
    quotations: list[ComparisonRow]
