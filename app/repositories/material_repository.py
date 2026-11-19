from collections.abc import Iterable

from sqlalchemy import func, select

from app.models import Material
from app.repositories.base import BaseRepository, apply_sort

SORTABLE = {
    "name": Material.name,
    "sku": Material.sku,
    "category": Material.category,
    "unit_price": Material.unit_price,
}


class MaterialRepository(BaseRepository[Material]):
    model = Material

    def get_by_sku(self, sku: str) -> Material | None:
        return self.db.scalar(select(Material).where(func.lower(Material.sku) == sku.lower()))

    def get_many(self, ids: Iterable[int]) -> dict[int, Material]:
        id_list = list(set(ids))
        if not id_list:
            return {}
        rows = self.db.scalars(select(Material).where(Material.id.in_(id_list))).all()
        return {m.id: m for m in rows}

    def search(
        self,
        *,
        search: str | None,
        category: str | None,
        sort_by: str,
        order: str,
        page: int,
        limit: int,
    ) -> tuple[list[Material], int]:
        stmt = select(Material)
        if search:
            stmt = stmt.where(
                Material.name.icontains(search, autoescape=True)
                | Material.sku.icontains(search, autoescape=True)
            )
        if category:
            stmt = stmt.where(func.lower(Material.category) == category.lower())
        stmt = apply_sort(stmt, SORTABLE, sort_by, order, Material.id)
        return self.paginate(stmt, page, limit)
