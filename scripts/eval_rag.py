"""Evaluate retrieval quality.  Usage: python -m scripts.eval_rag [--min-hit-rate 0.8]

Exits with status 1 when the hit rate is below the threshold, so it can gate CI/deployments.
"""

import argparse
import json
import sys
from pathlib import Path

from app.db.session import SessionLocal
from app.schemas.knowledge import EvalCaseIn, EvaluateRequest
from app.services.rag.knowledge_service import KnowledgeService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="data/rag_eval.json")
    parser.add_argument("--min-hit-rate", type=float, default=0.8)
    args = parser.parse_args()

    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    request = EvaluateRequest(
        cases=[EvalCaseIn(**case) for case in dataset["cases"]], top_k=dataset.get("top_k", 3)
    )
    with SessionLocal() as db:
        report = KnowledgeService(db).evaluate(request)

    for r in report["results"]:
        mark = "ok  " if r["hit"] else "MISS"
        print(f"{mark} rank={r['first_relevant_rank']} {r['question']}")
    print(f"\nhit_rate@{report['top_k']}={report['hit_rate']}  mrr={report['mrr']}  precision@k={report['precision_at_k']}")
    if report["hit_rate"] < args.min_hit_rate:
        print(f"FAILED: hit rate below {args.min_hit_rate}")
        sys.exit(1)


if __name__ == "__main__":
    main()
