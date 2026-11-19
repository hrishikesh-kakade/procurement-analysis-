from fastapi import APIRouter

from app.api.deps import AnalyticsSvc, Range
from app.schemas.analytics import (
    AveragePO,
    DepartmentSpend,
    MonthlySpend,
    RejectionRate,
    SupplierPerformance,
    SupplierScorecard,
    TotalSpend,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/total-spend", response_model=TotalSpend)
def total_spend(service: AnalyticsSvc, rng: Range):
    """Total value of committed purchase orders (issued, partially received, received)."""
    return service.total_spend(rng)


@router.get("/average-po", response_model=AveragePO)
def average_po(service: AnalyticsSvc, rng: Range):
    return service.average_po(rng)


@router.get("/rejection-rate", response_model=RejectionRate)
def rejection_rate(service: AnalyticsSvc, rng: Range):
    """Share of decided requisitions that were rejected, by decision date."""
    return service.rejection_rate(rng)


@router.get("/suppliers", response_model=list[SupplierPerformance])
def supplier_performance(service: AnalyticsSvc, rng: Range):
    """Per-supplier spend, order count and fulfilment rate (received / ordered units)."""
    return service.supplier_performance(rng)


@router.get("/monthly-spend", response_model=list[MonthlySpend])
def monthly_spend(service: AnalyticsSvc, rng: Range):
    return service.monthly_spend(rng)


@router.get("/department-spend", response_model=list[DepartmentSpend])
def department_spend(service: AnalyticsSvc, rng: Range):
    return service.department_spend(rng)


@router.get("/supplier-scorecard", response_model=list[SupplierScorecard])
def supplier_scorecard(service: AnalyticsSvc, rng: Range):
    """Weighted score (0-100): fulfilment 40%, on-time delivery 40%, RFQ win rate 20%."""
    return service.supplier_scorecard(rng)
