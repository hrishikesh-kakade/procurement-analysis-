"""CSV report generation (runs inside a background worker when Redis is configured)."""

import csv
import io
from collections.abc import Callable
from datetime import date

from sqlalchemy.orm import Session

from app.repositories.purchase_order_repository import PurchaseOrderRepository
from app.schemas.common import DateRange
from app.services.analytics_service import AnalyticsService

REPORT_TYPES = (
    "supplier_performance",
    "supplier_scorecard",
    "monthly_spend",
    "department_spend",
    "purchase_orders",
)


def _to_csv(columns: list[str], rows: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: ("" if row.get(c) is None else row.get(c)) for c in columns})
    return buffer.getvalue()


def build_report_csv(db: Session, report_type: str, rng: DateRange) -> str:
    analytics = AnalyticsService(db)
    builders: dict[str, Callable[[], str]] = {
        "supplier_performance": lambda: _to_csv(
            ["supplier_id", "supplier_name", "order_count", "total_spend", "average_po_value", "fulfillment_rate_percent"],
            analytics.supplier_performance(rng),
        ),
        "supplier_scorecard": lambda: _to_csv(
            ["supplier_id", "supplier_name", "order_count", "total_spend", "fulfillment_rate_percent",
             "on_time_delivery_rate_percent", "quotation_win_rate_percent", "score", "rating"],
            analytics.supplier_scorecard(rng),
        ),
        "monthly_spend": lambda: _to_csv(
            ["month", "total_spend", "order_count"], analytics.monthly_spend(rng)
        ),
        "department_spend": lambda: _to_csv(
            ["department", "total_spend", "order_count"], analytics.department_spend(rng)
        ),
        "purchase_orders": lambda: _purchase_orders(db, rng),
    }
    return builders[report_type]()


def _purchase_orders(db: Session, rng: DateRange) -> str:
    orders, _ = PurchaseOrderRepository(db).search(
        status=None,
        supplier_id=None,
        date_from=rng.date_from,
        date_to=rng.date_to,
        sort_by="order_date",
        order="asc",
        page=1,
        limit=100_000,
    )
    rows = [
        {
            "po_number": o.po_number,
            "supplier_id": o.supplier_id,
            "status": str(o.status),
            "order_date": o.order_date.isoformat(),
            "expected_delivery_date": o.expected_delivery_date.isoformat() if o.expected_delivery_date else "",
            "total_amount": o.total_amount,
        }
        for o in orders
    ]
    return _to_csv(
        ["po_number", "supplier_id", "status", "order_date", "expected_delivery_date", "total_amount"],
        rows,
    )


def parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None
