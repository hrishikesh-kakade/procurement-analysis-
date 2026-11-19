import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.cache import invalidate_analytics
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.money import line_total, order_total
from app.core.numbering import generate_number
from app.models import Quotation, QuotationItem, Rfq, RfqItem
from app.models.enums import QuotationStatus, RequisitionStatus, RfqStatus, SupplierStatus
from app.repositories.material_repository import MaterialRepository
from app.repositories.requisition_repository import RequisitionRepository
from app.repositories.rfq_repository import RfqRepository
from app.repositories.supplier_repository import SupplierRepository
from app.schemas.common import DateRange
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderItemCreate
from app.schemas.rfq import QuotationCreate, RfqCreate
from app.services.analytics_service import AnalyticsService
from app.services.purchase_order_service import PurchaseOrderService
from app.services.workflow import RFQ_TRANSITIONS, ensure_transition

logger = logging.getLogger(__name__)

# Composite ranking weights (points out of 100).
WEIGHTS = {"price": 50, "delivery": 25, "supplier_score": 25}


class RfqService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = RfqRepository(db)
        self.suppliers = SupplierRepository(db)
        self.materials = MaterialRepository(db)
        self.requisitions = RequisitionRepository(db)
        self.orders = PurchaseOrderService(db)

    # ---- queries -----------------------------------------------------------------------
    def get(self, rfq_id: int) -> Rfq:
        rfq = self.repo.get(rfq_id)
        if rfq is None:
            raise NotFoundError("RFQ", rfq_id)
        return rfq

    def search(self, **filters) -> tuple[list[Rfq], int]:
        return self.repo.search(**filters)

    # ---- lifecycle ---------------------------------------------------------------------
    def create(self, data: RfqCreate) -> Rfq:
        if data.due_date and data.due_date < date.today():
            raise BusinessRuleError("due_date cannot be in the past")
        lines = [(i.material_id, i.quantity) for i in data.items]
        if data.requisition_id is not None:
            requisition = self.requisitions.get(data.requisition_id)
            if requisition is None:
                raise NotFoundError("Requisition", data.requisition_id)
            if requisition.status != RequisitionStatus.APPROVED:
                raise ConflictError(
                    "Only approved requisitions can be sourced through an RFQ "
                    f"(current status: '{requisition.status}')"
                )
            if not lines:
                lines = [(i.material_id, i.quantity) for i in requisition.items]
        found = self.materials.get_many(m for m, _ in lines)
        missing = sorted({m for m, _ in lines} - found.keys())
        if missing:
            raise NotFoundError("Material", ", ".join(map(str, missing)))
        rfq = Rfq(
            rfq_number=generate_number("RFQ"),
            title=data.title,
            description=data.description,
            requisition_id=data.requisition_id,
            due_date=data.due_date,
            status=RfqStatus.DRAFT,
            items=[RfqItem(material_id=m, quantity=q) for m, q in lines],
        )
        self.repo.add(rfq)
        return self._save(rfq, "rfq created")

    def publish(self, rfq_id: int) -> Rfq:
        return self._transition(rfq_id, RfqStatus.PUBLISHED)

    def close(self, rfq_id: int) -> Rfq:
        return self._transition(rfq_id, RfqStatus.CLOSED)

    def cancel(self, rfq_id: int) -> Rfq:
        return self._transition(rfq_id, RfqStatus.CANCELLED)

    # ---- quotations --------------------------------------------------------------------
    def submit_quotation(self, rfq_id: int, data: QuotationCreate) -> Quotation:
        rfq = self.get(rfq_id)
        if rfq.status != RfqStatus.PUBLISHED:
            raise ConflictError(
                f"Quotations can only be submitted while the RFQ is published (status: '{rfq.status}')"
            )
        if rfq.due_date and rfq.due_date < date.today():
            raise BusinessRuleError("The RFQ due date has passed")
        supplier = self.suppliers.get(data.supplier_id)
        if supplier is None:
            raise NotFoundError("Supplier", data.supplier_id)
        if supplier.status != SupplierStatus.ACTIVE:
            raise BusinessRuleError(f"Supplier is '{supplier.status}' and cannot quote")
        if any(q.supplier_id == supplier.id for q in rfq.quotations):
            raise ConflictError("This supplier has already submitted a quotation for the RFQ")

        rfq_items = {i.id: i for i in rfq.items}
        prices = {i.rfq_item_id: i.unit_price for i in data.items}
        if set(prices) != set(rfq_items):
            raise BusinessRuleError("A quotation must price every RFQ item exactly once")

        items = [
            QuotationItem(
                rfq_item_id=item_id,
                unit_price=price,
                line_total=line_total(rfq_items[item_id].quantity, price),
            )
            for item_id, price in prices.items()
        ]
        quotation = Quotation(
            rfq_id=rfq.id,
            supplier_id=supplier.id,
            status=QuotationStatus.SUBMITTED,
            delivery_days=data.delivery_days,
            notes=data.notes,
            total_amount=order_total(i.line_total for i in items),
            items=items,
        )
        self.db.add(quotation)
        self.db.commit()
        invalidate_analytics()
        self.db.refresh(quotation)
        logger.info("quotation submitted id=%s rfq=%s", quotation.id, rfq.id)
        return quotation

    def list_quotations(self, rfq_id: int) -> list[Quotation]:
        return list(self.get(rfq_id).quotations)

    def compare(self, rfq_id: int) -> dict:
        """Rank quotations: price 50 pts, delivery speed 25 pts, supplier scorecard 25 pts."""
        rfq = self.get(rfq_id)
        quotations = list(rfq.quotations)
        if not quotations:
            return {"rfq_id": rfq.id, "recommended_quotation_id": None, "weights": WEIGHTS, "quotations": []}

        scores = {
            row["supplier_id"]: row["score"]
            for row in AnalyticsService(self.db).supplier_scorecard(DateRange())
        }
        names = {q.supplier_id: self.suppliers.get(q.supplier_id).name for q in quotations}
        lowest_total = min(q.total_amount for q in quotations)
        fastest = min(q.delivery_days for q in quotations)

        rows = []
        for q in quotations:
            score = scores.get(q.supplier_id)
            price_pts = WEIGHTS["price"] * (float(lowest_total / q.total_amount) if q.total_amount else 1.0)
            delivery_pts = WEIGHTS["delivery"] * (fastest + 1) / (q.delivery_days + 1)
            supplier_pts = WEIGHTS["supplier_score"] * ((score / 100) if score is not None else 0.5)
            rows.append(
                {
                    "quotation_id": q.id,
                    "supplier_id": q.supplier_id,
                    "supplier_name": names[q.supplier_id],
                    "status": q.status,
                    "total_amount": q.total_amount,
                    "delivery_days": q.delivery_days,
                    "supplier_score": score,
                    "price_points": round(price_pts, 2),
                    "delivery_points": round(delivery_pts, 2),
                    "supplier_points": round(supplier_pts, 2),
                    "composite_score": round(price_pts + delivery_pts + supplier_pts, 2),
                }
            )
        rows.sort(key=lambda r: (-r["composite_score"], r["total_amount"]))
        for rank, row in enumerate(rows, start=1):
            row["rank"] = rank
        return {
            "rfq_id": rfq.id,
            "recommended_quotation_id": rows[0]["quotation_id"],
            "weights": WEIGHTS,
            "quotations": rows,
        }

    def award(self, rfq_id: int, quotation_id: int) -> Rfq:
        rfq = self.get(rfq_id)
        ensure_transition(RFQ_TRANSITIONS, rfq.status, RfqStatus.AWARDED, "RFQ")
        winner = next((q for q in rfq.quotations if q.id == quotation_id), None)
        if winner is None:
            raise NotFoundError("Quotation", quotation_id)

        rfq_items = {i.id: i for i in rfq.items}
        requisition = self.requisitions.get(rfq.requisition_id) if rfq.requisition_id else None
        link_requisition = requisition is not None and requisition.status == RequisitionStatus.APPROVED
        order = self.orders.create(
            PurchaseOrderCreate(
                supplier_id=winner.supplier_id,
                requisition_id=requisition.id if link_requisition else None,
                expected_delivery_date=date.today() + timedelta(days=winner.delivery_days),
                notes=f"Awarded from {rfq.rfq_number}",
                items=[
                    PurchaseOrderItemCreate(
                        material_id=rfq_items[qi.rfq_item_id].material_id,
                        quantity=rfq_items[qi.rfq_item_id].quantity,
                        unit_price=qi.unit_price,
                    )
                    for qi in winner.items
                ],
            ),
            commit=False,  # same transaction as the status changes below
        )
        for q in rfq.quotations:
            q.status = QuotationStatus.ACCEPTED if q.id == winner.id else QuotationStatus.REJECTED
        rfq.status = RfqStatus.AWARDED
        rfq.awarded_po_id = order.id
        return self._save(rfq, "rfq awarded")

    # ---- helpers -----------------------------------------------------------------------
    def _transition(self, rfq_id: int, target: RfqStatus) -> Rfq:
        rfq = self.get(rfq_id)
        ensure_transition(RFQ_TRANSITIONS, rfq.status, target, "RFQ")
        if target == RfqStatus.PUBLISHED and not rfq.items:
            raise BusinessRuleError("Cannot publish an RFQ without items")
        rfq.status = target
        return self._save(rfq, f"rfq {target}")

    def _save(self, rfq: Rfq, event: str) -> Rfq:
        self.db.commit()
        invalidate_analytics()
        self.db.refresh(rfq)
        logger.info("%s id=%s status=%s", event, rfq.id, rfq.status)
        return rfq
