from fastapi import APIRouter, status

from app.api.deps import Pagination, UserSvc
from app.api.permissions import CurrentUser
from app.models.enums import UserRole
from app.schemas.common import Page, build_page
from app.schemas.user import UserCreate, UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Users (admin)"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, service: UserSvc):
    return service.create(payload)


@router.get("", response_model=Page[UserRead], summary="List users")
def list_users(
    service: UserSvc,
    pagination: Pagination,
    role: UserRole | None = None,
    is_active: bool | None = None,
):
    items, total = service.search(
        role=role, is_active=is_active, page=pagination.page, limit=pagination.limit
    )
    return build_page(items, total, pagination)


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, service: UserSvc):
    return service.get(user_id)


@router.patch("/{user_id}", response_model=UserRead, summary="Change role, name or active state")
def update_user(user_id: int, payload: UserUpdate, service: UserSvc, admin: CurrentUser):
    return service.update(user_id, payload, admin)
