import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.cache import invalidate_analytics
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.numbering import generate_number
from app.models import Requisition, RequisitionItem
from app.models.enums import RequisitionStatus
from app.repositories.material_repository import MaterialRepository
from app.repositories.requisition_repository import RequisitionRepository
from app.schemas.requisition import (
    RequisitionCreate,
    RequisitionItemCreate,
    RequisitionPatch,
)
from app.services.workflow import REQUISITION_TRANSITIONS, ensure_transition

logger = logging.getLogger(__name__)


class RequisitionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = RequisitionRepository(db)
        self.materials = MaterialRepository(db)

    # ---- queries -------------------------------------------------------------------------
    def get(self, requisition_id: int) -> Requisition:
        requisition = self.repo.get(requisition_id)
        if requisition is None:
            raise NotFoundError("Requisition", requisition_id)
        return requisition

    def search(self, **filters) -> tuple[list[Requisition], int]:
        return self.repo.search(**filters)

    # ---- drafting ------------------------------------------------------------------------
    def create(self, data: RequisitionCreate) -> Requisition:
        requisition = Requisition(
            requisition_number=generate_number("REQ"),
            department=data.department,
            requested_by=data.requested_by,
            justification=data.justification,
            status=RequisitionStatus.DRAFT,
            items=self._build_items(data.items),
        )
        self.repo.add(requisition)
        return self._save(requisition, "requisition created")

    def replace(self, requisition_id: int, data: RequisitionCreate) -> Requisition:
        requisition = self._get_draft(requisition_id)
        requisition.department = data.department
        requisition.requested_by = data.requested_by
        requisition.justification = data.justification
        requisition.items = self._build_items(data.items)
        return self._save(requisition, "requisition replaced")

    def patch(self, requisition_id: int, data: RequisitionPatch) -> Requisition:
        requisition = self._get_draft(requisition_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None or field == "justification":
                setattr(requisition, field, value)
        return self._save(requisition, "requisition updated")

    def add_item(self, requisition_id: int, item: RequisitionItemCreate) -> Requisition:
        requisition = self._get_draft(requisition_id)
        if any(existing.material_id == item.material_id for existing in requisition.items):
            raise ConflictError(f"Material {item.material_id} is already on this requisition")
        requisition.items.append(self._build_items([item])[0])
        return self._save(requisition, "requisition item added")

    def remove_item(self, requisition_id: int, item_id: int) -> Requisition:
        requisition = self._get_draft(requisition_id)
        target = next((i for i in requisition.items if i.id == item_id), None)
        if target is None:
            raise NotFoundError("Requisition item", item_id)
        requisition.items.remove(target)
        return self._save(requisition, "requisition item removed")

    def delete(self, requisition_id: int) -> None:
        requisition = self._get_draft(requisition_id)
        self.repo.delete(requisition)
        self.db.commit()
        invalidate_analytics()
        logger.info("requisition deleted id=%s", requisition_id)

    # ---- workflow ------------------------------------------------------------------------
    def submit(self, requisition_id: int) -> Requisition:
        requisition = self.get(requisition_id)
        ensure_transition(
            REQUISITION_TRANSITIONS, requisition.status, RequisitionStatus.SUBMITTED, "requisition"
        )
        if not requisition.items:
            raise BusinessRuleError("Cannot submit a requisition without items")
        requisition.status = RequisitionStatus.SUBMITTED
        requisition.submitted_at = datetime.now(UTC)
        return self._save(requisition, "requisition submitted")

    def approve(self, requisition_id: int) -> Requisition:
        requisition = self.get(requisition_id)
        ensure_transition(
            REQUISITION_TRANSITIONS, requisition.status, RequisitionStatus.APPROVED, "requisition"
        )
        requisition.status = RequisitionStatus.APPROVED
        requisition.decided_at = datetime.now(UTC)
        return self._save(requisition, "requisition approved")

    def reject(self, requisition_id: int, reason: str) -> Requisition:
        requisition = self.get(requisition_id)
        ensure_transition(
            REQUISITION_TRANSITIONS, requisition.status, RequisitionStatus.REJECTED, "requisition"
        )
        requisition.status = RequisitionStatus.REJECTED
        requisition.rejection_reason = reason
        requisition.decided_at = datetime.now(UTC)
        return self._save(requisition, "requisition rejected")

    # ---- helpers -------------------------------------------------------------------------
    def _get_draft(self, requisition_id: int) -> Requisition:
        requisition = self.get(requisition_id)
        if requisition.status != RequisitionStatus.DRAFT:
            raise ConflictError(
                f"Requisition is '{requisition.status}'; only draft requisitions can be modified"
            )
        return requisition

    def _build_items(self, items: list[RequisitionItemCreate]) -> list[RequisitionItem]:
        found = self.materials.get_many(i.material_id for i in items)
        missing = sorted({i.material_id for i in items} - found.keys())
        if missing:
            raise NotFoundError("Material", ", ".join(map(str, missing)))
        return [
            RequisitionItem(
                material_id=i.material_id,
                quantity=i.quantity,
                estimated_unit_price=(
                    i.estimated_unit_price
                    if i.estimated_unit_price is not None
                    else found[i.material_id].unit_price
                ),
            )
            for i in items
        ]

    def _save(self, requisition: Requisition, event: str) -> Requisition:
        self.db.commit()
        invalidate_analytics()
        self.db.refresh(requisition)
        logger.info("%s id=%s status=%s", event, requisition.id, requisition.status)
        return requisition
