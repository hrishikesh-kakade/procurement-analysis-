from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DeliveryItemCreate(BaseModel):
    po_item_id: int = Field(gt=0)
    quantity_received: int = Field(gt=0)


class DeliveryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    received_date: date | None = None
    received_by: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=2000)
    items: list[DeliveryItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def _no_duplicate_items(self) -> "DeliveryCreate":
        ids = [item.po_item_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate po_item_id in items")
        return self


class DeliveryItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    po_item_id: int
    quantity_received: int


class DeliveryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    purchase_order_id: int
    received_date: date
    received_by: str | None
    notes: str | None
    items: list[DeliveryItemRead]
    created_at: datetime
