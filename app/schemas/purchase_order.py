from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import PurchaseOrderStatus
from app.schemas.common import Money


class PurchaseOrderItemCreate(BaseModel):
    material_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    unit_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Defaults to the material's catalogue price",
    )


class PurchaseOrderCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    supplier_id: int = Field(gt=0)
    requisition_id: int | None = Field(
        default=None, gt=0, description="Approved requisition to convert into this order"
    )
    order_date: date | None = None
    expected_delivery_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    items: list[PurchaseOrderItemCreate] = Field(
        default_factory=list,
        description="Optional when requisition_id is supplied (items are copied from it)",
    )

    @model_validator(mode="after")
    def _validate_items(self) -> "PurchaseOrderCreate":
        if not self.items and self.requisition_id is None:
            raise ValueError("items are required when requisition_id is not provided")
        ids = [item.material_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate material_id in items")
        return self


class PurchaseOrderStatusUpdate(BaseModel):
    status: PurchaseOrderStatus


class PurchaseOrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    quantity: int
    unit_price: Money
    line_total: Money
    received_quantity: int


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_number: str
    supplier_id: int
    requisition_id: int | None
    status: PurchaseOrderStatus
    total_amount: Money
    order_date: date
    expected_delivery_date: date | None
    notes: str | None
    items: list[PurchaseOrderItemRead]
    created_at: datetime
    updated_at: datetime
