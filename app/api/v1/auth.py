from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import UserSvc
from app.api.permissions import CurrentUser
from app.core.config import get_settings
from app.core.security import create_access_token
from app.schemas.user import PasswordChange, Token, UserRead

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token, summary="Obtain a JWT access token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], service: UserSvc):
    """Form fields: `username` (the user's e-mail) and `password`."""
    user = service.authenticate(form.username, form.password)
    settings = get_settings()
    return Token(
        access_token=create_access_token(user.id, user.role),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserRead, summary="Current user")
def me(user: CurrentUser):
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(payload: PasswordChange, user: CurrentUser, service: UserSvc):
    service.change_password(user, payload.current_password, payload.new_password)
