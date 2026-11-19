import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, PlainSerializer

T = TypeVar("T")

# Money is validated as Decimal but serialised to JSON as a plain number.
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    limit: int
    pages: int


@dataclass(frozen=True)
class PaginationParams:
    page: int
    limit: int


@dataclass(frozen=True)
class DateRange:
    date_from: date | None = None
    date_to: date | None = None


def build_page(items: list[Any], total: int, params: PaginationParams) -> dict[str, Any]:
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "limit": params.limit,
        "pages": math.ceil(total / params.limit) if total else 0,
    }
