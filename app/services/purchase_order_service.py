import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.cache import invalidate_analytics
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.money import line_total, order_total, quantize_money
from app.core.numbering import generate_number
from app.models import PurchaseOrder, PurchaseOrderItem
from app.models.enums import PurchaseOrderStatus, RequisitionStatus, SupplierStatus
from app.repositories.material_repository import MaterialRepository
from app.repositories.purchase_order_repository import PurchaseOrderRepository
from app.repositories.requisition_repository import RequisitionRepository
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.purchase_order import PurchaseOrderCreate
from app.services.workflow import PURCHASE_ORDER_TRANSITIONS, ensure_transition

logger = logging.getLogger(__name__)
_AUTOMATIC_STATUSES = {PurchaseOrderStatus.PARTIALLY_RECEIVED, PurchaseOrderStatus.RECEIVED}


class PurchaseOrderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PurchaseOrderRepository(db)
        self.suppliers = SupplierRepository(db)
        self.materials = MaterialRepository(db)
        self.requisitions = RequisitionRepository(db)

    def get(self, po_id: int) -> PurchaseOrder:
        order = self.repo.get(po_id)
        if order is None:
            raise NotFoundError("Purchase order", po_id)
        return order

    def search(self, **filters) -> tuple[list[PurchaseOrder], int]:
        return self.repo.search(**filters)

    def create(self, data: PurchaseOrderCreate, *, commit: bool = True) -> PurchaseOrder:
        supplier = self.suppliers.get(data.supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier", data.supplier_id)
        if supplier.status != SupplierStatus.ACTIVE:
            raise BusinessRuleError(
                f"Supplier is '{supplier.status}'; orders can only be placed with active suppliers"
            )

        order_date = data.order_date or date.today()
        if data.expected_delivery_date and data.expected_delivery_date < order_date:
            raise BusinessRuleError("expected_delivery_date cannot be before order_date")

        lines = [(i.material_id, i.quantity, i.unit_price) for i in data.items]
        requisition = None
        if data.requisition_id is not None:
            requisition = self.requisitions.get(data.requisition_id)
            if requisition is None:
                raise NotFoundError("Requisition", data.requisition_id)
            if requisition.status != RequisitionStatus.APPROVED:
                raise ConflictError(
                    "Only approved requisitions can be converted into purchase orders "
                    f"(current status: '{requisition.status}')"
                )
            if not lines:
                lines = [
                    (i.material_id, i.quantity, i.estimated_unit_price) for i in requisition.items
                ]
        if not lines:
            raise BusinessRuleError("A purchase order needs at least one item")

        materials = self.materials.get_many(material_id for material_id, _, _ in lines)
        missing = sorted({m for m, _, _ in lines} - materials.keys())
        if missing:
            raise NotFoundError("Material", ", ".join(map(str, missing)))

        items = []
        for material_id, quantity, price in lines:
            unit_price = quantize_money(price if price is not None else materials[material_id].unit_price)
            items.append(
                PurchaseOrderItem(
                    material_id=material_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total(quantity, unit_price),
                    received_quantity=0,
                )
            )

        order = PurchaseOrder(
            po_number=generate_number("PO"),
            supplier_id=supplier.id,
            requisition_id=requisition.id if requisition else None,
            status=PurchaseOrderStatus.DRAFT,
            order_date=order_date,
            expected_delivery_date=data.expected_delivery_date,
            notes=data.notes,
            items=items,
            total_amount=order_total(i.line_total for i in items),  # always computed server-side
        )
        if requisition:
            requisition.status = RequisitionStatus.CONVERTED
        self.repo.add(order)
        if commit:
            self.db.commit()
            invalidate_analytics()
            self.db.refresh(order)
        logger.info("purchase order created id=%s total=%s", order.id, order.total_amount)
        return order

    def update_status(self, po_id: int, target: PurchaseOrderStatus) -> PurchaseOrder:
        order = self.get(po_id)
        if target in _AUTOMATIC_STATUSES:
            raise BusinessRuleError(
                "Receipt statuses are set automatically when deliveries are recorded"
            )
        ensure_transition(PURCHASE_ORDER_TRANSITIONS, order.status, target, "purchase order")
        order.status = target
        self.db.commit()
        invalidate_analytics()
        self.db.refresh(order)
        logger.info("purchase order id=%s status=%s", order.id, order.status)
        return order
