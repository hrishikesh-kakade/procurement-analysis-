from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.api.deps import DbSession
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import decode_access_token
from app.models import User
from app.models.enums import UserRole as R

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(token: Annotated[str | None, Depends(oauth2_scheme)], db: DbSession) -> User:
    if not token:
        raise AuthenticationError("Not authenticated")
    payload = decode_access_token(token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("Invalid token") from exc
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: R):
    allowed = frozenset(roles)

    def checker(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise AuthorizationError(f"Role '{user.role}' is not permitted to perform this action")
        return user

    return Depends(checker)


# Permission sets (each also implies authentication).
ADMIN_ONLY = [require_roles(R.ADMIN)]
MANAGE = [require_roles(R.ADMIN, R.PROCUREMENT_MANAGER)]
REQUISITION_WRITE = [require_roles(R.ADMIN, R.PROCUREMENT_MANAGER, R.REQUESTER)]
APPROVE = [require_roles(R.ADMIN, R.PROCUREMENT_MANAGER, R.APPROVER)]
ANALYTICS_READ = [require_roles(R.ADMIN, R.PROCUREMENT_MANAGER, R.APPROVER, R.VIEWER)]
AUTHENTICATED = [Depends(get_current_user)]
