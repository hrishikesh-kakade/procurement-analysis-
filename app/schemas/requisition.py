from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import RequisitionStatus
from app.schemas.common import Money


class RequisitionItemCreate(BaseModel):
    material_id: int = Field(gt=0)
    quantity: int = Field(gt=0, description="Must be greater than zero")
    estimated_unit_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=12,
        decimal_places=2,
        description="Defaults to the material's catalogue price",
    )


class RequisitionBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    department: str = Field(min_length=2, max_length=100, examples=["Engineering"])
    requested_by: str = Field(min_length=2, max_length=100)
    justification: str | None = Field(default=None, max_length=2000)


class RequisitionCreate(RequisitionBase):
    items: list[RequisitionItemCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def _no_duplicate_materials(self) -> "RequisitionCreate":
        ids = [item.material_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate material_id in items")
        return self


class RequisitionPatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    department: str | None = Field(default=None, min_length=2, max_length=100)
    requested_by: str | None = Field(default=None, min_length=2, max_length=100)
    justification: str | None = Field(default=None, max_length=2000)


class RejectRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    reason: str = Field(min_length=3, max_length=2000)


class RequisitionItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    material_id: int
    quantity: int
    estimated_unit_price: Money
    line_total: Money


class RequisitionRead(RequisitionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requisition_number: str
    status: RequisitionStatus
    rejection_reason: str | None
    submitted_at: datetime | None
    decided_at: datetime | None
    total_estimated_amount: Money
    items: list[RequisitionItemRead]
    created_at: datetime
    updated_at: datetime
