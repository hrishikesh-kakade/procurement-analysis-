from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import Pagination, SupplierSvc
from app.models.enums import SupplierStatus
from app.schemas.common import Page, build_page
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate

from app.api.permissions import MANAGE

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.post("", dependencies=MANAGE, response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, service: SupplierSvc):
    return service.create(payload)


@router.get("", response_model=Page[SupplierRead], summary="List suppliers")
def list_suppliers(
    service: SupplierSvc,
    pagination: Pagination,
    search: Annotated[str | None, Query(description="Case-insensitive name search")] = None,
    category: Annotated[str | None, Query(description="Exact category (case-insensitive)")] = None,
    status_filter: Annotated[SupplierStatus | None, Query(alias="status")] = None,
    sort_by: Literal["name", "category", "status", "created_at"] = "created_at",
    order: Literal["asc", "desc"] = "desc",
):
    items, total = service.search(
        search=search,
        category=category,
        status=status_filter,
        sort_by=sort_by,
        order=order,
        page=pagination.page,
        limit=pagination.limit,
    )
    return build_page(items, total, pagination)


@router.get("/{supplier_id}", response_model=SupplierRead)
def get_supplier(supplier_id: int, service: SupplierSvc):
    return service.get(supplier_id)


@router.put("/{supplier_id}", dependencies=MANAGE, response_model=SupplierRead, summary="Replace a supplier")
def replace_supplier(supplier_id: int, payload: SupplierCreate, service: SupplierSvc):
    return service.replace(supplier_id, payload)


@router.patch("/{supplier_id}", dependencies=MANAGE, response_model=SupplierRead, summary="Partially update a supplier")
def patch_supplier(supplier_id: int, payload: SupplierUpdate, service: SupplierSvc):
    return service.patch(supplier_id, payload)


@router.delete("/{supplier_id}", dependencies=MANAGE, status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(supplier_id: int, service: SupplierSvc):
    service.delete(supplier_id)
