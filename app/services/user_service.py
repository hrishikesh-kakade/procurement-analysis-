import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, BusinessRuleError, ConflictError, NotFoundError
from app.core.security import DUMMY_HASH, hash_password, verify_password
from app.models import User
from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = UserRepository(db)

    def get(self, user_id: int) -> User:
        user = self.repo.get(user_id)
        if user is None:
            raise NotFoundError("User", user_id)
        return user

    def search(self, **filters) -> tuple[list[User], int]:
        return self.repo.search(**filters)

    def create(self, data: UserCreate) -> User:
        email = str(data.email).lower()
        if self.repo.get_by_email(email):
            raise ConflictError(f"A user with email '{email}' already exists")
        user = self.repo.add(
            User(
                email=email,
                full_name=data.full_name,
                hashed_password=hash_password(data.password),
                role=data.role,
            )
        )
        self.db.commit()
        self.db.refresh(user)
        logger.info("user created id=%s role=%s", user.id, user.role)
        return user

    def update(self, user_id: int, data: UserUpdate, acting_user: User) -> User:
        user = self.get(user_id)
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        if user.id == acting_user.id and (
            changes.get("is_active") is False or ("role" in changes and changes["role"] != user.role)
        ):
            raise BusinessRuleError("You cannot change your own role or deactivate your own account")
        for field, value in changes.items():
            setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        logger.info("user updated id=%s", user.id)
        return user

    def authenticate(self, email: str, password: str) -> User:
        user = self.repo.get_by_email(email.strip())
        password_ok = verify_password(password, user.hashed_password if user else DUMMY_HASH)
        if user is None or not password_ok or not user.is_active:
            raise AuthenticationError("Incorrect email or password")
        user.last_login_at = datetime.now(UTC)
        self.db.commit()
        return user

    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise BusinessRuleError("Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        self.db.commit()
        logger.info("password changed user=%s", user.id)


def ensure_bootstrap_admin(db: Session, email: str, password: str) -> None:
    """Create the first admin account when the users table is empty."""
    repo = UserRepository(db)
    if repo.count() > 0:
        return
    repo.add(
        User(
            email=email.lower(),
            full_name="Administrator",
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
        )
    )
    db.commit()
    logger.info("bootstrap admin created")
