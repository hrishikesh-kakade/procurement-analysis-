from datetime import date
from typing import Literal

from pydantic import BaseModel, model_validator

ReportType = Literal[
    "supplier_performance", "supplier_scorecard", "monthly_spend", "department_spend", "purchase_orders"
]


class ReportRequest(BaseModel):
    report_type: ReportType
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def _check_range(self) -> "ReportRequest":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must not be after date_to")
        return self


class ReportJob(BaseModel):
    job_id: str
    report_type: str | None
    status: str
    mode: str
