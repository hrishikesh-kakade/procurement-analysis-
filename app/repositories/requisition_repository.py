from sqlalchemy import func, select

from app.models import Requisition
from app.models.enums import RequisitionStatus
from app.repositories.base import BaseRepository, apply_sort

SORTABLE = {
    "created_at": Requisition.created_at,
    "department": Requisition.department,
    "status": Requisition.status,
    "requisition_number": Requisition.requisition_number,
}


class RequisitionRepository(BaseRepository[Requisition]):
    model = Requisition

    def search(
        self,
        *,
        department: str | None,
        status: RequisitionStatus | None,
        sort_by: str,
        order: str,
        page: int,
        limit: int,
    ) -> tuple[list[Requisition], int]:
        stmt = select(Requisition)
        if department:
            stmt = stmt.where(func.lower(Requisition.department) == department.lower())
        if status:
            stmt = stmt.where(Requisition.status == status)
        stmt = apply_sort(stmt, SORTABLE, sort_by, order, Requisition.id)
        return self.paginate(stmt, page, limit)
