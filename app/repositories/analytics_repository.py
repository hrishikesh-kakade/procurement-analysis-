from datetime import UTC, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import Select, case, desc, extract, func, literal_column, select
from sqlalchemy.orm import Session

from app.models import (
    Delivery,
    PurchaseOrder,
    PurchaseOrderItem,
    Quotation,
    Requisition,
    Rfq,
    Supplier,
)
from app.models.enums import PurchaseOrderStatus, QuotationStatus, RequisitionStatus, RfqStatus
from app.schemas.common import DateRange

# Orders that represent committed spend (drafts and cancelled orders are excluded).
SPEND_STATUSES = (
    PurchaseOrderStatus.ISSUED,
    PurchaseOrderStatus.PARTIALLY_RECEIVED,
    PurchaseOrderStatus.RECEIVED,
)
DECIDED_STATUSES = (
    RequisitionStatus.APPROVED,
    RequisitionStatus.REJECTED,
    RequisitionStatus.CONVERTED,
)


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _spend_conditions(rng: DateRange) -> list:
    conditions = [PurchaseOrder.status.in_(SPEND_STATUSES)]
    if rng.date_from:
        conditions.append(PurchaseOrder.order_date >= rng.date_from)
    if rng.date_to:
        conditions.append(PurchaseOrder.order_date <= rng.date_to)
    return conditions


class AnalyticsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def spend_totals(self, rng: DateRange) -> tuple[Decimal, int]:
        stmt: Select = select(func.sum(PurchaseOrder.total_amount), func.count(PurchaseOrder.id))
        total, count = self.db.execute(stmt.where(*_spend_conditions(rng))).one()
        return _money(total), int(count or 0)

    def requisition_decisions(self, rng: DateRange) -> tuple[int, int]:
        conditions = [Requisition.status.in_(DECIDED_STATUSES)]
        if rng.date_from:
            lower = datetime.combine(rng.date_from, time.min, tzinfo=UTC)
            conditions.append(Requisition.decided_at >= lower)
        if rng.date_to:
            upper = datetime.combine(rng.date_to + timedelta(days=1), time.min, tzinfo=UTC)
            conditions.append(Requisition.decided_at < upper)
        decided = self.db.scalar(select(func.count(Requisition.id)).where(*conditions)) or 0
        rejected = (
            self.db.scalar(
                select(func.count(Requisition.id)).where(
                    *conditions, Requisition.status == RequisitionStatus.REJECTED
                )
            )
            or 0
        )
        return int(decided), int(rejected)

    def supplier_performance(self, rng: DateRange) -> list[dict]:
        conditions = _spend_conditions(rng)
        orders = self.db.execute(
            select(
                Supplier.id,
                Supplier.name,
                func.count(PurchaseOrder.id),
                func.sum(PurchaseOrder.total_amount),
            )
            .join(PurchaseOrder, PurchaseOrder.supplier_id == Supplier.id)
            .where(*conditions)
            .group_by(Supplier.id, Supplier.name)
        ).all()
        quantities = {
            supplier_id: (int(ordered or 0), int(received or 0))
            for supplier_id, ordered, received in self.db.execute(
                select(
                    PurchaseOrder.supplier_id,
                    func.sum(PurchaseOrderItem.quantity),
                    func.sum(PurchaseOrderItem.received_quantity),
                )
                .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
                .where(*conditions)
                .group_by(PurchaseOrder.supplier_id)
            ).all()
        }
        result = []
        for supplier_id, name, order_count, total in orders:
            ordered, received = quantities.get(supplier_id, (0, 0))
            result.append(
                {
                    "supplier_id": supplier_id,
                    "supplier_name": name,
                    "order_count": int(order_count),
                    "total_spend": _money(total),
                    "ordered_quantity": ordered,
                    "received_quantity": received,
                }
            )
        return result

    def monthly_spend(self, rng: DateRange) -> list[dict]:
        year = extract("year", PurchaseOrder.order_date)
        month = extract("month", PurchaseOrder.order_date)
        rows = self.db.execute(
            select(
                year.label("y"),
                month.label("m"),
                func.sum(PurchaseOrder.total_amount),
                func.count(PurchaseOrder.id),
            )
            .where(*_spend_conditions(rng))
            .group_by(year, month)
            .order_by(year, month)
        ).all()
        return [
            {"month": f"{int(y):04d}-{int(m):02d}", "total_spend": _money(t), "order_count": int(c)}
            for y, m, t, c in rows
        ]

    def department_spend(self, rng: DateRange) -> list[dict]:
        department = func.coalesce(Requisition.department, literal_column("'Unassigned'"))
        total = func.sum(PurchaseOrder.total_amount)
        rows = self.db.execute(
            select(department.label("department"), total.label("total"), func.count(PurchaseOrder.id))
            .select_from(PurchaseOrder)
            .outerjoin(Requisition, PurchaseOrder.requisition_id == Requisition.id)
            .where(*_spend_conditions(rng))
            .group_by(department)
            .order_by(desc(total))
        ).all()
        return [
            {"department": d, "total_spend": _money(t), "order_count": int(c)} for d, t, c in rows
        ]

    def on_time_stats(self, rng: DateRange) -> dict[int, tuple[int, int]]:
        """supplier_id -> (fully received orders with a promised date, of which delivered on time)."""
        last_delivery = func.max(Delivery.received_date)
        rows = self.db.execute(
            select(PurchaseOrder.supplier_id, PurchaseOrder.expected_delivery_date, last_delivery)
            .join(Delivery, Delivery.purchase_order_id == PurchaseOrder.id)
            .where(
                *_spend_conditions(rng),
                PurchaseOrder.status == PurchaseOrderStatus.RECEIVED,
                PurchaseOrder.expected_delivery_date.is_not(None),
            )
            .group_by(
                PurchaseOrder.id, PurchaseOrder.supplier_id, PurchaseOrder.expected_delivery_date
            )
        ).all()
        stats: dict[int, tuple[int, int]] = {}
        for supplier_id, expected, last in rows:
            total, on_time = stats.get(supplier_id, (0, 0))
            stats[supplier_id] = (total + 1, on_time + (1 if last <= expected else 0))
        return stats

    def quotation_stats(self) -> dict[int, tuple[int, int]]:
        """supplier_id -> (quotations in awarded RFQs, of which won)."""
        rows = self.db.execute(
            select(
                Quotation.supplier_id,
                func.count(Quotation.id),
                func.sum(case((Quotation.status == QuotationStatus.ACCEPTED, 1), else_=0)),
            )
            .join(Rfq, Rfq.id == Quotation.rfq_id)
            .where(Rfq.status == RfqStatus.AWARDED)
            .group_by(Quotation.supplier_id)
        ).all()
        return {supplier_id: (int(total), int(won or 0)) for supplier_id, total, won in rows}

    def supplier_names(self) -> dict[int, str]:
        return {sid: name for sid, name in self.db.execute(select(Supplier.id, Supplier.name))}
