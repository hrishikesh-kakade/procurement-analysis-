from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Money


class MaterialBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sku: str = Field(min_length=2, max_length=50, examples=["ELEC-0001"])
    name: str = Field(min_length=2, max_length=150)
    category: str = Field(min_length=2, max_length=80)
    unit: str = Field(default="each", min_length=1, max_length=20)
    unit_price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=2, max_length=150)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)


class MaterialRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    category: str
    unit: str
    unit_price: Money
    created_at: datetime
    updated_at: datetime
