import pytest

from app.core.exceptions import ExternalServiceError
from app.models.enums import UserRole as R
from app.services.assistant.llm import LLMResponse, ToolCall
from tests.factories import API, create_material, create_purchase_order, create_supplier, set_po_status


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, system, messages, tools=None, max_tokens=1024):
        self.calls.append({"system": system, "messages": list(messages), "tools": tools})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _tool_response(name="get_total_spend", args=None, call_id="t1"):
    call = ToolCall(id=call_id, name=name, input=args or {})
    return LLMResponse(
        text="", tool_calls=[call],
        content=[{"type": "tool_use", "id": call_id, "name": name, "input": args or {}}],
    )


def _chat(client, message="What is our total spend?", history=None):
    return client.post(f"{API}/assistant/chat", json={"message": message, "history": history or []})


def _issue_order(client, quantity=5, price="10.00"):
    supplier, material = create_supplier(client), create_material(client)
    order = create_purchase_order(
        client, supplier["id"], items=[{"material_id": material["id"], "quantity": quantity, "unit_price": price}]
    )
    set_po_status(client, order["id"], "issued")


def test_rule_based_fallback_answers_from_real_data(client):
    _issue_order(client, quantity=5, price="10.00")
    body = _chat(client).json()
    assert body["provider"] == "rules"
    assert body["tools_used"][0]["name"] == "get_total_spend"
    assert "50.00" in body["answer"] and "1 orders" in body["answer"]


@pytest.mark.parametrize(
    ("question", "tool"),
    [
        ("What is the rejection rate?", "get_rejection_rate"),
        ("show the monthly trend", "get_monthly_spend"),
        ("spend by department", "get_department_spend"),
        ("which suppliers perform best", "get_supplier_performance"),
        ("show the supplier scorecard", "get_supplier_scorecard"),
        ("what is the average order value", "get_average_po"),
    ],
)
def test_rule_based_intent_routing(client, question, tool):
    assert _chat(client, question).json()["tools_used"][0]["name"] == tool


def test_unknown_question_returns_help_without_tools(client):
    body = _chat(client, "tell me a joke").json()
    assert body["tools_used"] == [] and "I can answer" in body["answer"]


def test_llm_tool_loop(client, monkeypatch):
    _issue_order(client, quantity=2, price="25.00")
    fake = FakeLLM([_tool_response(), LLMResponse(text="Total spend is 50.")])
    monkeypatch.setattr("app.services.assistant.llm.get_llm", lambda: fake)

    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]
    body = _chat(client, history=history).json()
    assert body == {"answer": "Total spend is 50.", "tools_used": [{"name": "get_total_spend", "input": {}}], "provider": "llm"}

    first, second = fake.calls
    assert first["tools"] and "ONLY data returned by your tools" in first["system"]
    assert [m["role"] for m in first["messages"]] == ["user", "assistant", "user"]
    tool_result = second["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "t1"
    assert "50.00" in tool_result["content"]


def test_unknown_tool_and_bad_dates_are_handled_gracefully(client, monkeypatch):
    fake = FakeLLM(
        [
            _tool_response("drop_all_tables", call_id="t1"),
            _tool_response("get_total_spend", {"date_from": "yesterday"}, call_id="t2"),
            LLMResponse(text="Sorry, I could not do that."),
        ]
    )
    monkeypatch.setattr("app.services.assistant.llm.get_llm", lambda: fake)
    body = _chat(client).json()
    assert body["answer"] == "Sorry, I could not do that."
    results = [c["messages"][-1]["content"][0]["content"] for c in fake.calls[1:]]
    assert "Unknown tool" in results[0] and "YYYY-MM-DD" in results[1]


def test_tool_loop_is_bounded(client, monkeypatch):
    fake = FakeLLM([_tool_response(call_id=f"t{i}") for i in range(5)])
    monkeypatch.setattr("app.services.assistant.llm.get_llm", lambda: fake)
    body = _chat(client).json()
    assert "allowed steps" in body["answer"] and len(fake.calls) == 5


def test_llm_outage_returns_502(client, monkeypatch):
    fake = FakeLLM([ExternalServiceError("The AI service is currently unavailable")])
    monkeypatch.setattr("app.services.assistant.llm.get_llm", lambda: fake)
    response = _chat(client)
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "external_service_error"


def test_assistant_validation_and_permissions(client, make_client):
    assert client.post(f"{API}/assistant/chat", json={"message": ""}).status_code == 422
    too_long = [{"role": "user", "content": "x"}] * 11
    assert client.post(f"{API}/assistant/chat", json={"message": "hi", "history": too_long}).status_code == 422
    assert _chat(make_client(R.REQUESTER)).status_code == 403
    assert _chat(make_client(R.VIEWER)).status_code == 200
