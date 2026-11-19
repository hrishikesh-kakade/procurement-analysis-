from sqlalchemy import select

from app.models import Rfq
from app.models.enums import RfqStatus
from app.repositories.base import BaseRepository, apply_sort

SORTABLE = {
    "created_at": Rfq.created_at,
    "due_date": Rfq.due_date,
    "status": Rfq.status,
    "rfq_number": Rfq.rfq_number,
}


class RfqRepository(BaseRepository[Rfq]):
    model = Rfq

    def search(
        self, *, status: RfqStatus | None, sort_by: str, order: str, page: int, limit: int
    ) -> tuple[list[Rfq], int]:
        stmt = select(Rfq)
        if status:
            stmt = stmt.where(Rfq.status == status)
        stmt = apply_sort(stmt, SORTABLE, sort_by, order, Rfq.id)
        return self.paginate(stmt, page, limit)
