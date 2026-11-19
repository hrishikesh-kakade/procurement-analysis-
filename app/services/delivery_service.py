import logging
from datetime import date

from sqlalchemy.orm import Session

from app.core.cache import invalidate_analytics
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models import Delivery, DeliveryItem
from app.models.enums import PurchaseOrderStatus
from app.repositories.purchase_order_repository import PurchaseOrderRepository
from app.schemas.delivery import DeliveryCreate
from app.services.workflow import PURCHASE_ORDER_TRANSITIONS, ensure_transition

logger = logging.getLogger(__name__)
_RECEIVABLE = (PurchaseOrderStatus.ISSUED, PurchaseOrderStatus.PARTIALLY_RECEIVED)


class DeliveryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.orders = PurchaseOrderRepository(db)

    def list_for_order(self, po_id: int) -> list[Delivery]:
        if self.orders.get(po_id) is None:
            raise NotFoundError("Purchase order", po_id)
        return self.orders.list_deliveries(po_id)

    def record(self, po_id: int, data: DeliveryCreate) -> Delivery:
        order = self.orders.get_for_update(po_id)
        if order is None:
            raise NotFoundError("Purchase order", po_id)
        if order.status not in _RECEIVABLE:
            raise ConflictError(
                f"Deliveries can only be recorded for issued orders (current status: '{order.status}')"
            )

        items_by_id = {item.id: item for item in order.items}
        delivery = Delivery(
            purchase_order_id=order.id,
            received_date=data.received_date or date.today(),
            received_by=data.received_by,
            notes=data.notes,
        )
        for line in data.items:
            po_item = items_by_id.get(line.po_item_id)
            if po_item is None:
                raise BusinessRuleError(
                    f"Item {line.po_item_id} does not belong to purchase order {order.id}"
                )
            remaining = po_item.quantity - po_item.received_quantity
            if line.quantity_received > remaining:
                raise BusinessRuleError(
                    f"Cannot receive {line.quantity_received} units of item {po_item.id}; "
                    f"only {remaining} remaining"
                )
            po_item.received_quantity += line.quantity_received
            delivery.items.append(
                DeliveryItem(po_item_id=po_item.id, quantity_received=line.quantity_received)
            )

        fully_received = all(i.received_quantity == i.quantity for i in order.items)
        new_status = (
            PurchaseOrderStatus.RECEIVED if fully_received else PurchaseOrderStatus.PARTIALLY_RECEIVED
        )
        if new_status != order.status:
            ensure_transition(PURCHASE_ORDER_TRANSITIONS, order.status, new_status, "purchase order")
            order.status = new_status

        self.db.add(delivery)
        self.db.commit()
        invalidate_analytics()
        self.db.refresh(delivery)
        logger.info("delivery recorded id=%s po=%s status=%s", delivery.id, order.id, order.status)
        return delivery
