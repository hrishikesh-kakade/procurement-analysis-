from sqlalchemy import func, select

from app.models import User
from app.models.enums import UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(func.lower(User.email) == email.lower()))

    def count(self) -> int:
        return self.db.scalar(select(func.count(User.id))) or 0

    def search(
        self, *, role: UserRole | None, is_active: bool | None, page: int, limit: int
    ) -> tuple[list[User], int]:
        stmt = select(User)
        if role:
            stmt = stmt.where(User.role == role)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        return self.paginate(stmt.order_by(User.id), page, limit)
