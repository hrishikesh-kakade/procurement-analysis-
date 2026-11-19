from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, obj_id: int) -> ModelT | None:
        return self.db.get(self.model, obj_id)

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.flush()
        return obj

    def delete(self, obj: ModelT) -> None:
        self.db.delete(obj)
        self.db.flush()

    def paginate(self, stmt: Select[Any], page: int, limit: int) -> tuple[list[ModelT], int]:
        total = self.db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
        rows = self.db.scalars(stmt.offset((page - 1) * limit).limit(limit)).all()
        return list(rows), total or 0


def apply_sort(stmt: Select[Any], columns: dict[str, Any], sort_by: str, order: str, tiebreak: Any):
    column = columns[sort_by]
    primary = column.desc() if order == "desc" else column.asc()
    return stmt.order_by(primary, tiebreak.asc())
