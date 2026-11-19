import json
from datetime import date

from app.schemas.common import DateRange
from app.services.analytics_service import AnalyticsService

_DATE_PROPS = {
    "date_from": {"type": "string", "description": "Inclusive start date, YYYY-MM-DD (optional)"},
    "date_to": {"type": "string", "description": "Inclusive end date, YYYY-MM-DD (optional)"},
}


def _tool(name: str, description: str) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {"type": "object", "properties": _DATE_PROPS, "required": []},
    }


TOOLS = [
    _tool("get_total_spend", "Total committed purchase-order spend and number of orders."),
    _tool("get_average_po", "Average purchase order value."),
    _tool("get_rejection_rate", "Percentage of decided requisitions that were rejected."),
    _tool("get_supplier_performance", "Per-supplier spend, order count and fulfilment rate, highest spend first."),
    _tool("get_supplier_scorecard", "Weighted supplier scores (0-100) with A-D ratings."),
    _tool("get_monthly_spend", "Spend and order count per month."),
    _tool("get_department_spend", "Spend and order count per requesting department."),
]

_METHODS = {
    "get_total_spend": "total_spend",
    "get_average_po": "average_po",
    "get_rejection_rate": "rejection_rate",
    "get_supplier_performance": "supplier_performance",
    "get_supplier_scorecard": "supplier_scorecard",
    "get_monthly_spend": "monthly_spend",
    "get_department_spend": "department_spend",
}


def execute_tool(analytics: AnalyticsService, name: str, args: dict) -> dict | list:
    method = _METHODS.get(name)
    if method is None:
        return {"error": f"Unknown tool '{name}'"}
    try:
        rng = DateRange(
            date.fromisoformat(args["date_from"]) if args.get("date_from") else None,
            date.fromisoformat(args["date_to"]) if args.get("date_to") else None,
        )
    except ValueError:
        return {"error": "Dates must be formatted as YYYY-MM-DD"}
    result = getattr(analytics, method)(rng)
    return json.loads(json.dumps(result, default=str))  # plain JSON types for the model
