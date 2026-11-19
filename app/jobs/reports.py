"""RQ job entry points. Executed by the worker process: `rq worker reports`."""

from app.db.session import SessionLocal
from app.schemas.common import DateRange
from app.services.report_service import build_report_csv, parse_date


def run_report(report_type: str, date_from: str | None, date_to: str | None) -> str:
    rng = DateRange(parse_date(date_from), parse_date(date_to))
    with SessionLocal() as db:
        return build_report_csv(db, report_type, rng)
