"""Retrieval evaluation: hit-rate@k, MRR and precision@k over a labelled question set."""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.services.rag.vector_store import Hit


@dataclass
class EvalCase:
    question: str
    expected_titles: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)


def is_relevant(hit: Hit, case: EvalCase) -> bool:
    if any(t.lower() == hit.title.lower() for t in case.expected_titles):
        return True
    text = hit.text.lower()
    return bool(case.expected_keywords) and all(k.lower() in text for k in case.expected_keywords)


def evaluate_retrieval(
    cases: list[EvalCase], search: Callable[[str, int], list[Hit]], top_k: int
) -> dict:
    results = []
    for case in cases:
        hits = search(case.question, top_k)
        relevance = [is_relevant(h, case) for h in hits]
        first = next((i for i, ok in enumerate(relevance, start=1) if ok), None)
        results.append(
            {
                "question": case.question,
                "hit": first is not None,
                "first_relevant_rank": first,
                "reciprocal_rank": 1 / first if first else 0.0,
                "precision_at_k": sum(relevance) / top_k,
                "top_titles": [h.title for h in hits],
            }
        )
    n = len(results) or 1
    return {
        "cases": len(results),
        "top_k": top_k,
        "hit_rate": round(sum(r["hit"] for r in results) / n, 4),
        "mrr": round(sum(r["reciprocal_rank"] for r in results) / n, 4),
        "precision_at_k": round(sum(r["precision_at_k"] for r in results) / n, 4),
        "results": results,
    }
