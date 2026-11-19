from datetime import date

from pydantic import BaseModel

from app.schemas.common import Money


class TotalSpend(BaseModel):
    total_spend: Money
    order_count: int
    date_from: date | None
    date_to: date | None


class AveragePO(BaseModel):
    average_po_value: Money
    order_count: int
    date_from: date | None
    date_to: date | None


class RejectionRate(BaseModel):
    decided_count: int
    rejected_count: int
    rejection_rate_percent: float
    date_from: date | None
    date_to: date | None


class SupplierPerformance(BaseModel):
    supplier_id: int
    supplier_name: str
    order_count: int
    total_spend: Money
    average_po_value: Money
    fulfillment_rate_percent: float


class MonthlySpend(BaseModel):
    month: str
    total_spend: Money
    order_count: int


class DepartmentSpend(BaseModel):
    department: str
    total_spend: Money
    order_count: int


class SupplierScorecard(BaseModel):
    supplier_id: int
    supplier_name: str
    order_count: int
    total_spend: Money
    fulfillment_rate_percent: float | None
    on_time_delivery_rate_percent: float | None
    quotation_win_rate_percent: float | None
    score: float | None
    rating: str | None
