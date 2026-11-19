import json
import re
from pathlib import Path

import pytest

from app.models.enums import UserRole as R
from app.services.assistant.llm import LLMResponse
from tests.test_assistant import FakeLLM

API = "/api/v1/knowledge"
DATA = Path(__file__).resolve().parents[1] / "data"


def _docs():
    for path in sorted((DATA / "knowledge").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        yield re.match(r"#\s+(.+)", text).group(1).strip(), text, path.name


@pytest.fixture
def kb(client):
    for title, text, name in _docs():
        response = client.post(f"{API}/documents", json={"title": title, "content": text, "source_name": name})
        assert response.status_code == 201, response.text
    return client


def test_ingest_lists_documents_and_rejects_duplicates(kb):
    listing = kb.get(f"{API}/documents").json()
    assert listing["total"] == 4 and all(d["chunk_count"] >= 1 for d in listing["items"])
    title, text, _ = next(_docs())
    assert kb.post(f"{API}/documents", json={"title": title, "content": text}).status_code == 409


def test_search_returns_the_relevant_document_first(kb):
    hits = kb.post(f"{API}/search", json={"query": "approval limit for requisitions", "top_k": 3}).json()
    assert hits[0]["title"] == "Requisition Approval Matrix"
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True)


def test_ask_without_llm_is_extractive_and_cited(kb):
    body = kb.post(f"{API}/ask", json={"question": "Can goods received exceed the quantity ordered?"}).json()
    assert body["provider"] == "extractive" and body["grounded"] is True
    assert body["citations"][0]["marker"] == 1
    assert body["citations"][0]["title"] == "Receiving Goods and Payment"
    assert "[1]" in body["answer"]


def test_ask_off_topic_question_finds_nothing(kb):
    body = kb.post(f"{API}/ask", json={"question": "What is the airspeed velocity of an unladen swallow?"}).json()
    assert body["grounded"] is False and body["citations"] == []
    assert "could not find" in body["answer"]


def test_ask_with_llm_returns_only_valid_citations(kb, monkeypatch):
    fake = FakeLLM([LLMResponse(text="Rejected requisitions cannot be approved later [1][2][9].")])
    monkeypatch.setattr("app.services.assistant.llm.get_llm", lambda: fake)
    body = kb.post(f"{API}/ask", json={"question": "Can a rejected requisition be approved later?", "top_k": 3}).json()
    assert body["provider"] == "llm" and body["grounded"] is True
    assert [c["marker"] for c in body["citations"]] == [1, 2]  # [9] does not exist and is dropped
    prompt = fake.calls[0]["messages"][0]["content"]
    assert prompt.startswith("Context passages:") and "[1]" in prompt
    assert "ONLY the numbered context" in fake.calls[0]["system"]


def test_ask_marks_uncited_llm_answers_as_ungrounded(kb, monkeypatch):
    fake = FakeLLM([LLMResponse(text="Approvals are probably fine.")])
    monkeypatch.setattr("app.services.assistant.llm.get_llm", lambda: fake)
    body = kb.post(f"{API}/ask", json={"question": "Who approves requisitions?"}).json()
    assert body["grounded"] is False and body["citations"] == []


def test_retrieval_evaluation_meets_quality_bar(kb):
    dataset = json.loads((DATA / "rag_eval.json").read_text(encoding="utf-8"))
    report = kb.post(f"{API}/evaluate", json={**dataset, "with_answers": True}).json()
    assert report["cases"] == 10
    assert report["hit_rate"] >= 0.8 and report["mrr"] >= 0.7
    assert report["grounded_rate"] == 1.0
    assert all("first_relevant_rank" in r for r in report["results"])


def test_deleting_a_document_removes_it_from_search(kb):
    documents = kb.get(f"{API}/documents").json()["items"]
    policy = next(d for d in documents if d["title"] == "Procurement Policy")
    assert kb.delete(f"{API}/documents/{policy['id']}").status_code == 204
    hits = kb.post(f"{API}/search", json={"query": "When is an RFQ required?", "top_k": 5}).json()
    assert all(h["title"] != "Procurement Policy" for h in hits)
    assert kb.get(f"{API}/documents").json()["total"] == 3
    assert kb.delete(f"{API}/documents/{policy['id']}").status_code == 404


def test_file_upload(client):
    content = ("# Travel Policy\n\nEmployees book travel through approved vendors only. " * 3).encode()
    ok = client.post(f"{API}/documents/upload", files={"file": ("travel.md", content, "text/markdown")}, data={"title": "Travel Policy"})
    assert ok.status_code == 201 and ok.json()["title"] == "Travel Policy"
    binary = client.post(f"{API}/documents/upload", files={"file": ("bad.txt", b"\xff\xfe\x00\x01" * 50, "text/plain")})
    assert binary.status_code == 422


def test_knowledge_permissions(kb, make_client):
    viewer = make_client(R.VIEWER)
    assert viewer.post(f"{API}/ask", json={"question": "Who approves requisitions?"}).status_code == 200
    assert viewer.post(f"{API}/search", json={"query": "payment terms"}).status_code == 200
    doc = {"title": "Sneaky", "content": "x" * 50}
    assert viewer.post(f"{API}/documents", json=doc).status_code == 403
    assert viewer.post(f"{API}/evaluate", json={"cases": [{"question": "q q q"}]}).status_code == 403
    assert viewer.delete(f"{API}/documents/1").status_code == 403
