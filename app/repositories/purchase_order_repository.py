from datetime import date

from sqlalchemy import select

from app.models import Delivery, PurchaseOrder
from app.models.enums import PurchaseOrderStatus
from app.repositories.base import BaseRepository, apply_sort

SORTABLE = {
    "created_at": PurchaseOrder.created_at,
    "order_date": PurchaseOrder.order_date,
    "total_amount": PurchaseOrder.total_amount,
    "status": PurchaseOrder.status,
}


class PurchaseOrderRepository(BaseRepository[PurchaseOrder]):
    model = PurchaseOrder

    def get_for_update(self, po_id: int) -> PurchaseOrder | None:
        """Load with a row lock (SELECT ... FOR UPDATE on PostgreSQL) to serialise receipts."""
        return self.db.get(PurchaseOrder, po_id, with_for_update=True)

    def search(
        self,
        *,
        status: PurchaseOrderStatus | None,
        supplier_id: int | None,
        date_from: date | None,
        date_to: date | None,
        sort_by: str,
        order: str,
        page: int,
        limit: int,
    ) -> tuple[list[PurchaseOrder], int]:
        stmt = select(PurchaseOrder)
        if status:
            stmt = stmt.where(PurchaseOrder.status == status)
        if supplier_id:
            stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
        if date_from:
            stmt = stmt.where(PurchaseOrder.order_date >= date_from)
        if date_to:
            stmt = stmt.where(PurchaseOrder.order_date <= date_to)
        stmt = apply_sort(stmt, SORTABLE, sort_by, order, PurchaseOrder.id)
        return self.paginate(stmt, page, limit)

    def list_deliveries(self, po_id: int) -> list[Delivery]:
        stmt = select(Delivery).where(Delivery.purchase_order_id == po_id).order_by(Delivery.id)
        return list(self.db.scalars(stmt).all())
