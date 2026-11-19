from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import Pagination, RequisitionSvc
from app.models.enums import RequisitionStatus
from app.schemas.common import Page, build_page
from app.schemas.requisition import (
    RejectRequest,
    RequisitionCreate,
    RequisitionItemCreate,
    RequisitionPatch,
    RequisitionRead,
)

from app.api.permissions import APPROVE, REQUISITION_WRITE

router = APIRouter(prefix="/requisitions", tags=["Purchase Requisitions"])


@router.post("", dependencies=REQUISITION_WRITE, response_model=RequisitionRead, status_code=status.HTTP_201_CREATED)
def create_requisition(payload: RequisitionCreate, service: RequisitionSvc):
    return service.create(payload)


@router.get("", response_model=Page[RequisitionRead], summary="List requisitions")
def list_requisitions(
    service: RequisitionSvc,
    pagination: Pagination,
    department: str | None = None,
    status_filter: Annotated[RequisitionStatus | None, Query(alias="status")] = None,
    sort_by: Literal["created_at", "department", "status", "requisition_number"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
):
    items, total = service.search(
        department=department,
        status=status_filter,
        sort_by=sort_by,
        order=order,
        page=pagination.page,
        limit=pagination.limit,
    )
    return build_page(items, total, pagination)


@router.get("/{requisition_id}", response_model=RequisitionRead)
def get_requisition(requisition_id: int, service: RequisitionSvc):
    return service.get(requisition_id)


@router.put("/{requisition_id}", dependencies=REQUISITION_WRITE, response_model=RequisitionRead, summary="Replace a draft")
def replace_requisition(requisition_id: int, payload: RequisitionCreate, service: RequisitionSvc):
    return service.replace(requisition_id, payload)


@router.patch("/{requisition_id}", dependencies=REQUISITION_WRITE, response_model=RequisitionRead, summary="Update draft header")
def patch_requisition(requisition_id: int, payload: RequisitionPatch, service: RequisitionSvc):
    return service.patch(requisition_id, payload)


@router.delete("/{requisition_id}", dependencies=REQUISITION_WRITE, status_code=status.HTTP_204_NO_CONTENT)
def delete_requisition(requisition_id: int, service: RequisitionSvc):
    service.delete(requisition_id)


@router.post(
    "/{requisition_id}/items", dependencies=REQUISITION_WRITE,
    response_model=RequisitionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an item to a draft requisition",
)
def add_item(requisition_id: int, payload: RequisitionItemCreate, service: RequisitionSvc):
    return service.add_item(requisition_id, payload)


@router.delete(
    "/{requisition_id}/items/{item_id}", dependencies=REQUISITION_WRITE,
    response_model=RequisitionRead,
    summary="Remove an item from a draft requisition",
)
def remove_item(requisition_id: int, item_id: int, service: RequisitionSvc):
    return service.remove_item(requisition_id, item_id)


@router.post("/{requisition_id}/submit", dependencies=REQUISITION_WRITE, response_model=RequisitionRead)
def submit_requisition(requisition_id: int, service: RequisitionSvc):
    return service.submit(requisition_id)


@router.post("/{requisition_id}/approve", dependencies=APPROVE, response_model=RequisitionRead)
def approve_requisition(requisition_id: int, service: RequisitionSvc):
    return service.approve(requisition_id)


@router.post("/{requisition_id}/reject", dependencies=APPROVE, response_model=RequisitionRead)
def reject_requisition(requisition_id: int, payload: RejectRequest, service: RequisitionSvc):
    return service.reject(requisition_id, payload.reason)
