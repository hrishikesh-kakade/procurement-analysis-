from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import Pagination, RfqSvc
from app.api.permissions import MANAGE
from app.models.enums import RfqStatus
from app.schemas.common import Page, build_page
from app.schemas.rfq import (
    QuotationCreate,
    QuotationRead,
    RfqAward,
    RfqComparison,
    RfqCreate,
    RfqRead,
)

router = APIRouter(prefix="/rfqs", tags=["RFQ & Quotations"])


@router.post("", dependencies=MANAGE, response_model=RfqRead, status_code=status.HTTP_201_CREATED)
def create_rfq(payload: RfqCreate, service: RfqSvc):
    """Create an RFQ from explicit items or from an approved requisition."""
    return service.create(payload)


@router.get("", response_model=Page[RfqRead], summary="List RFQs")
def list_rfqs(
    service: RfqSvc,
    pagination: Pagination,
    status_filter: Annotated[RfqStatus | None, Query(alias="status")] = None,
    sort_by: Literal["created_at", "due_date", "status", "rfq_number"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
):
    items, total = service.search(
        status=status_filter,
        sort_by=sort_by,
        order=order,
        page=pagination.page,
        limit=pagination.limit,
    )
    return build_page(items, total, pagination)


@router.get("/{rfq_id}", response_model=RfqRead)
def get_rfq(rfq_id: int, service: RfqSvc):
    return service.get(rfq_id)


@router.post("/{rfq_id}/publish", dependencies=MANAGE, response_model=RfqRead)
def publish_rfq(rfq_id: int, service: RfqSvc):
    return service.publish(rfq_id)


@router.post("/{rfq_id}/close", dependencies=MANAGE, response_model=RfqRead)
def close_rfq(rfq_id: int, service: RfqSvc):
    return service.close(rfq_id)


@router.post("/{rfq_id}/cancel", dependencies=MANAGE, response_model=RfqRead)
def cancel_rfq(rfq_id: int, service: RfqSvc):
    return service.cancel(rfq_id)


@router.post(
    "/{rfq_id}/quotations",
    dependencies=MANAGE,
    response_model=QuotationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a supplier quotation",
)
def submit_quotation(rfq_id: int, payload: QuotationCreate, service: RfqSvc):
    return service.submit_quotation(rfq_id, payload)


@router.get("/{rfq_id}/quotations", response_model=list[QuotationRead])
def list_quotations(rfq_id: int, service: RfqSvc):
    return service.list_quotations(rfq_id)


@router.get("/{rfq_id}/comparison", response_model=RfqComparison, summary="Rank quotations")
def compare_quotations(rfq_id: int, service: RfqSvc):
    """Composite ranking: price 50 pts, delivery speed 25 pts, supplier scorecard 25 pts."""
    return service.compare(rfq_id)


@router.post(
    "/{rfq_id}/award",
    dependencies=MANAGE,
    response_model=RfqRead,
    summary="Award a quotation and create the purchase order",
)
def award_rfq(rfq_id: int, payload: RfqAward, service: RfqSvc):
    return service.award(rfq_id, payload.quotation_id)
