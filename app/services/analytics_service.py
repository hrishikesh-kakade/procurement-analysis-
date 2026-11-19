from collections.abc import Callable
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core import cache as cache_module
from app.core.money import quantize_money
from app.repositories.analytics_repository import AnalyticsRepository
from app.schemas.common import DateRange

# Scorecard weights; metrics without data are dropped and the rest re-normalised.
SCORECARD_WEIGHTS = {"fulfillment": 0.4, "on_time": 0.4, "win_rate": 0.2}


def _rating(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def _range(rng: DateRange) -> dict:
    return {"date_from": rng.date_from, "date_to": rng.date_to}


class AnalyticsService:
    def __init__(self, db: Session, cache: cache_module.Cache | None = None) -> None:
        self.repo = AnalyticsRepository(db)
        self._cache = cache

    def _cached(self, name: str, rng: DateRange, producer: Callable[[], Any]) -> Any:
        cache = self._cache or cache_module.get_cache()
        return cache.get_or_set(
            "analytics", {"q": name, "from": rng.date_from, "to": rng.date_to}, producer
        )

    # ---- public API (each result is cached until analytics data changes) ----------------
    def total_spend(self, rng: DateRange) -> dict:
        return self._cached("total_spend", rng, lambda: self._total_spend(rng))

    def average_po(self, rng: DateRange) -> dict:
        return self._cached("average_po", rng, lambda: self._average_po(rng))

    def rejection_rate(self, rng: DateRange) -> dict:
        return self._cached("rejection_rate", rng, lambda: self._rejection_rate(rng))

    def supplier_performance(self, rng: DateRange) -> list[dict]:
        return self._cached("supplier_performance", rng, lambda: self._supplier_performance(rng))

    def monthly_spend(self, rng: DateRange) -> list[dict]:
        return self._cached("monthly_spend", rng, lambda: self.repo.monthly_spend(rng))

    def department_spend(self, rng: DateRange) -> list[dict]:
        return self._cached("department_spend", rng, lambda: self.repo.department_spend(rng))

    def supplier_scorecard(self, rng: DateRange) -> list[dict]:
        return self._cached("supplier_scorecard", rng, lambda: self._supplier_scorecard(rng))

    # ---- computations ---------------------------------------------------------------------
    def _total_spend(self, rng: DateRange) -> dict:
        total, count = self.repo.spend_totals(rng)
        return {"total_spend": total, "order_count": count, **_range(rng)}

    def _average_po(self, rng: DateRange) -> dict:
        total, count = self.repo.spend_totals(rng)
        average = quantize_money(total / count) if count else Decimal("0.00")
        return {"average_po_value": average, "order_count": count, **_range(rng)}

    def _rejection_rate(self, rng: DateRange) -> dict:
        decided, rejected = self.repo.requisition_decisions(rng)
        rate = round(rejected / decided * 100, 2) if decided else 0.0
        return {
            "decided_count": decided,
            "rejected_count": rejected,
            "rejection_rate_percent": rate,
            **_range(rng),
        }

    def _supplier_performance(self, rng: DateRange) -> list[dict]:
        rows = self.repo.supplier_performance(rng)
        for row in rows:
            row["average_po_value"] = quantize_money(row["total_spend"] / row["order_count"])
            ordered = row.pop("ordered_quantity")
            received = row.pop("received_quantity")
            row["fulfillment_rate_percent"] = round(received / ordered * 100, 2) if ordered else 0.0
        return sorted(rows, key=lambda r: r["total_spend"], reverse=True)

    def _supplier_scorecard(self, rng: DateRange) -> list[dict]:
        perf = {
            r["supplier_id"]: r
            for r in self._supplier_performance(rng)  # uncached: we are already inside a cache fill
        }
        on_time = self.repo.on_time_stats(rng)
        quotes = self.repo.quotation_stats()
        rows = []
        for supplier_id, name in self.repo.supplier_names().items():
            p = perf.get(supplier_id)
            fulfillment = p["fulfillment_rate_percent"] if p else None
            on_time_total, on_time_ok = on_time.get(supplier_id, (0, 0))
            on_time_rate = round(on_time_ok / on_time_total * 100, 2) if on_time_total else None
            quoted, won = quotes.get(supplier_id, (0, 0))
            win_rate = round(won / quoted * 100, 2) if quoted else None

            metrics = {"fulfillment": fulfillment, "on_time": on_time_rate, "win_rate": win_rate}
            available = {k: v for k, v in metrics.items() if v is not None}
            weight_sum = sum(SCORECARD_WEIGHTS[k] for k in available)
            score = (
                round(sum(SCORECARD_WEIGHTS[k] * v for k, v in available.items()) / weight_sum, 2)
                if available
                else None
            )
            rows.append(
                {
                    "supplier_id": supplier_id,
                    "supplier_name": name,
                    "order_count": p["order_count"] if p else 0,
                    "total_spend": p["total_spend"] if p else Decimal("0.00"),
                    "fulfillment_rate_percent": fulfillment,
                    "on_time_delivery_rate_percent": on_time_rate,
                    "quotation_win_rate_percent": win_rate,
                    "score": score,
                    "rating": _rating(score),
                }
            )
        return sorted(rows, key=lambda r: (r["score"] is None, -(r["score"] or 0), r["supplier_name"]))
