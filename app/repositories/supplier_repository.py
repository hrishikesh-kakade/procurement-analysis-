from sqlalchemy import func, select

from app.models import PurchaseOrder, Supplier
from app.models.enums import SupplierStatus
from app.repositories.base import BaseRepository, apply_sort

SORTABLE = {
    "name": Supplier.name,
    "category": Supplier.category,
    "status": Supplier.status,
    "created_at": Supplier.created_at,
}


class SupplierRepository(BaseRepository[Supplier]):
    model = Supplier

    def get_by_name(self, name: str) -> Supplier | None:
        return self.db.scalar(select(Supplier).where(func.lower(Supplier.name) == name.lower()))

    def get_by_email(self, email: str) -> Supplier | None:
        return self.db.scalar(select(Supplier).where(func.lower(Supplier.email) == email.lower()))

    def has_purchase_orders(self, supplier_id: int) -> bool:
        count = self.db.scalar(
            select(func.count(PurchaseOrder.id)).where(PurchaseOrder.supplier_id == supplier_id)
        )
        return bool(count)

    def search(
        self,
        *,
        search: str | None,
        category: str | None,
        status: SupplierStatus | None,
        sort_by: str,
        order: str,
        page: int,
        limit: int,
    ) -> tuple[list[Supplier], int]:
        stmt = select(Supplier)
        if search:
            stmt = stmt.where(Supplier.name.icontains(search, autoescape=True))
        if category:
            stmt = stmt.where(func.lower(Supplier.category) == category.lower())
        if status:
            stmt = stmt.where(Supplier.status == status)
        stmt = apply_sort(stmt, SORTABLE, sort_by, order, Supplier.id)
        return self.paginate(stmt, page, limit)
