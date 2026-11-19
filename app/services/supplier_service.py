import logging

from sqlalchemy.orm import Session

from app.core.cache import invalidate_analytics
from app.core.exceptions import ConflictError, NotFoundError
from app.models import Supplier
from app.models.enums import SupplierStatus
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.supplier import SupplierCreate, SupplierUpdate

logger = logging.getLogger(__name__)
_NULLABLE_FIELDS = {"phone", "address"}


class SupplierService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SupplierRepository(db)

    def get(self, supplier_id: int) -> Supplier:
        supplier = self.repo.get(supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier", supplier_id)
        return supplier

    def search(self, **filters) -> tuple[list[Supplier], int]:
        return self.repo.search(**filters)

    def create(self, data: SupplierCreate) -> Supplier:
        self._ensure_unique(data.name, str(data.email))
        supplier = self.repo.add(Supplier(**data.model_dump()))
        self.db.commit()
        invalidate_analytics()
        self.db.refresh(supplier)
        logger.info("supplier created id=%s", supplier.id)
        return supplier

    def replace(self, supplier_id: int, data: SupplierCreate) -> Supplier:
        supplier = self.get(supplier_id)
        self._ensure_unique(data.name, str(data.email), exclude_id=supplier_id)
        for field, value in data.model_dump().items():
            setattr(supplier, field, value)
        return self._save(supplier)

    def patch(self, supplier_id: int, data: SupplierUpdate) -> Supplier:
        supplier = self.get(supplier_id)
        changes = {
            k: v
            for k, v in data.model_dump(exclude_unset=True).items()
            if v is not None or k in _NULLABLE_FIELDS
        }
        self._ensure_unique(
            changes.get("name"), changes.get("email") and str(changes["email"]), supplier_id
        )
        for field, value in changes.items():
            setattr(supplier, field, value)
        return self._save(supplier)

    def delete(self, supplier_id: int) -> None:
        supplier = self.get(supplier_id)
        if self.repo.has_purchase_orders(supplier_id):
            raise ConflictError(
                "Supplier has purchase orders and cannot be deleted; "
                f"set its status to '{SupplierStatus.INACTIVE}' instead"
            )
        self.repo.delete(supplier)
        self.db.commit()
        invalidate_analytics()
        logger.info("supplier deleted id=%s", supplier_id)

    def _save(self, supplier: Supplier) -> Supplier:
        self.db.commit()
        invalidate_analytics()
        self.db.refresh(supplier)
        return supplier

    def _ensure_unique(self, name: str | None, email: str | None, exclude_id: int | None = None):
        if name:
            existing = self.repo.get_by_name(name)
            if existing and existing.id != exclude_id:
                raise ConflictError(f"A supplier named '{name}' already exists")
        if email:
            existing = self.repo.get_by_email(email)
            if existing and existing.id != exclude_id:
                raise ConflictError(f"A supplier with email '{email}' already exists")
