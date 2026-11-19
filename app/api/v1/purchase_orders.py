from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import DeliverySvc, Pagination, PurchaseOrderSvc
from app.models.enums import PurchaseOrderStatus
from app.schemas.common import Page, build_page
from app.schemas.delivery import DeliveryCreate, DeliveryRead
from app.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseOrderStatusUpdate,
)

from app.api.permissions import MANAGE

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.post("", dependencies=MANAGE, response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
def create_purchase_order(payload: PurchaseOrderCreate, service: PurchaseOrderSvc):
    """Create an order from explicit items, or from an approved requisition.

    Totals are always calculated by the backend.
    """
    return service.create(payload)


@router.get("", response_model=Page[PurchaseOrderRead], summary="List purchase orders")
def list_purchase_orders(
    service: PurchaseOrderSvc,
    pagination: Pagination,
    status_filter: Annotated[PurchaseOrderStatus | None, Query(alias="status")] = None,
    supplier_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: Literal["created_at", "order_date", "total_amount", "status"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
):
    items, total = service.search(
        status=status_filter,
        supplier_id=supplier_id,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        order=order,
        page=pagination.page,
        limit=pagination.limit,
    )
    return build_page(items, total, pagination)


@router.get("/{po_id}", response_model=PurchaseOrderRead)
def get_purchase_order(po_id: int, service: PurchaseOrderSvc):
    return service.get(po_id)


@router.patch("/{po_id}/status", dependencies=MANAGE, response_model=PurchaseOrderRead, summary="Issue or cancel an order")
def update_purchase_order_status(
    po_id: int, payload: PurchaseOrderStatusUpdate, service: PurchaseOrderSvc
):
    return service.update_status(po_id, payload.status)


@router.post(
    "/{po_id}/deliveries", dependencies=MANAGE,
    response_model=DeliveryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record received goods",
)
def record_delivery(po_id: int, payload: DeliveryCreate, service: DeliverySvc):
    return service.record(po_id, payload)


@router.get("/{po_id}/deliveries", response_model=list[DeliveryRead])
def list_deliveries(po_id: int, service: DeliverySvc):
    return service.list_for_order(po_id)
