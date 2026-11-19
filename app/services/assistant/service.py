import json
from datetime import date

from sqlalchemy.orm import Session

from app.services.analytics_service import AnalyticsService
from app.services.assistant import llm as llm_module
from app.services.assistant.tools import TOOLS, execute_tool

MAX_ROUNDS = 5
SYSTEM_PROMPT = (
    "You are the analytics assistant of a procurement platform. Answer questions about spend, "
    "suppliers, requisitions and purchase orders using ONLY data returned by your tools; never invent "
    "numbers. If the data needed is unavailable, say so. Be concise and use short bullet lists for "
    "rankings. Do not assume a currency - state amounts as plain numbers. Dates are YYYY-MM-DD. "
    "Today is {today}."
)

HELP_TEXT = (
    "I can answer questions such as: total spend, average order value, requisition rejection rate, "
    "monthly spend trend, spend by department, supplier performance and supplier scorecards."
)


class AssistantService:
    def __init__(self, db: Session) -> None:
        self.analytics = AnalyticsService(db)

    def chat(self, message: str, history: list[dict]) -> dict:
        llm = llm_module.get_llm()
        if llm is None:
            return self._rule_based(message)

        messages = [*history, {"role": "user", "content": message}]
        system = SYSTEM_PROMPT.format(today=date.today().isoformat())
        used: list[dict] = []
        for _ in range(MAX_ROUNDS):
            response = llm.generate(system, messages, TOOLS)
            if not response.tool_calls:
                return {"answer": response.text.strip() or "I have no answer for that.", "tools_used": used, "provider": "llm"}
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for call in response.tool_calls:
                used.append({"name": call.name, "input": call.input})
                payload = execute_tool(self.analytics, call.name, call.input)
                results.append(
                    {"type": "tool_result", "tool_use_id": call.id, "content": json.dumps(payload, default=str)}
                )
            messages.append({"role": "user", "content": results})
        return {
            "answer": "I could not complete that analysis within the allowed steps; please narrow the question.",
            "tools_used": used,
            "provider": "llm",
        }

    # ---- deterministic fallback (no API key configured) --------------------------------
    def _rule_based(self, message: str) -> dict:
        text = message.lower()
        tool, answer = None, HELP_TEXT
        if "reject" in text:
            tool = "get_rejection_rate"
        elif "scorecard" in text or "rating" in text or "score" in text:
            tool = "get_supplier_scorecard"
        elif "average" in text:
            tool = "get_average_po"
        elif "month" in text or "trend" in text:
            tool = "get_monthly_spend"
        elif "department" in text:
            tool = "get_department_spend"
        elif "supplier" in text or "vendor" in text:
            tool = "get_supplier_performance"
        elif "spend" in text or "total" in text:
            tool = "get_total_spend"
        used = []
        if tool:
            data = execute_tool(self.analytics, tool, {})
            used.append({"name": tool, "input": {}})
            answer = _format(tool, data)
        return {"answer": answer, "tools_used": used, "provider": "rules"}


def _money(value) -> str:
    return f"{float(value):,.2f}"


def _format(tool: str, data) -> str:
    if tool == "get_total_spend":
        return f"Total spend is {_money(data['total_spend'])} across {data['order_count']} orders."
    if tool == "get_average_po":
        return f"The average purchase order value is {_money(data['average_po_value'])} ({data['order_count']} orders)."
    if tool == "get_rejection_rate":
        return (
            f"{data['rejection_rate_percent']}% of decided requisitions were rejected "
            f"({data['rejected_count']} of {data['decided_count']})."
        )
    if not data:
        return "There is no data available yet for that question."
    if tool == "get_monthly_spend":
        return "Monthly spend:\n" + "\n".join(f"- {r['month']}: {_money(r['total_spend'])} ({r['order_count']} orders)" for r in data)
    if tool == "get_department_spend":
        return "Spend by department:\n" + "\n".join(f"- {r['department']}: {_money(r['total_spend'])}" for r in data)
    if tool == "get_supplier_scorecard":
        return "Supplier scorecard:\n" + "\n".join(
            f"- {r['supplier_name']}: {r['score'] if r['score'] is not None else 'n/a'} ({r['rating'] or '-'})" for r in data[:10]
        )
    return "Top suppliers by spend:\n" + "\n".join(
        f"- {r['supplier_name']}: {_money(r['total_spend'])}, fulfilment {r['fulfillment_rate_percent']}%" for r in data[:10]
    )
