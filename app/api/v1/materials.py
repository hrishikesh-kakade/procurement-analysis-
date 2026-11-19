from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import MaterialSvc, Pagination
from app.schemas.common import Page, build_page
from app.schemas.material import MaterialCreate, MaterialRead, MaterialUpdate

from app.api.permissions import MANAGE

router = APIRouter(prefix="/materials", tags=["Materials"])


@router.post("", dependencies=MANAGE, response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
def create_material(payload: MaterialCreate, service: MaterialSvc):
    return service.create(payload)


@router.get("", response_model=Page[MaterialRead], summary="List materials")
def list_materials(
    service: MaterialSvc,
    pagination: Pagination,
    search: Annotated[str | None, Query(description="Search by name or SKU")] = None,
    category: str | None = None,
    sort_by: Literal["name", "sku", "category", "unit_price"] = "name",
    order: Literal["asc", "desc"] = "asc",
):
    items, total = service.search(
        search=search,
        category=category,
        sort_by=sort_by,
        order=order,
        page=pagination.page,
        limit=pagination.limit,
    )
    return build_page(items, total, pagination)


@router.get("/{material_id}", response_model=MaterialRead)
def get_material(material_id: int, service: MaterialSvc):
    return service.get(material_id)


@router.patch("/{material_id}", dependencies=MANAGE, response_model=MaterialRead)
def patch_material(material_id: int, payload: MaterialUpdate, service: MaterialSvc):
    return service.patch(material_id, payload)
