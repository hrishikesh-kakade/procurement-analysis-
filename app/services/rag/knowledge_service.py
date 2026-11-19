import hashlib
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.embeddings import get_embedder
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.models import KnowledgeDocument, User
from app.repositories.base import BaseRepository
from app.schemas.knowledge import DocumentCreate, EvaluateRequest
from app.services.assistant import llm as llm_module
from app.services.rag.chunking import chunk_text
from app.services.rag.evaluation import EvalCase, evaluate_retrieval
from app.services.rag.vector_store import Hit, Point, get_vector_store

logger = logging.getLogger(__name__)
_CITATION = re.compile(r"\[(\d+)\]")

SYSTEM_PROMPT = (
    "You answer questions about the company's procurement policies using ONLY the numbered context "
    "passages provided. Cite the passages that support each statement using their numbers in square "
    "brackets, e.g. [1] or [2][3]. If the passages do not contain the answer, reply exactly: "
    "\"I could not find this in the knowledge base.\" Never use outside knowledge. Be concise."
)
NOT_FOUND = "I could not find this in the knowledge base."


class KnowledgeRepository(BaseRepository[KnowledgeDocument]):
    model = KnowledgeDocument


class KnowledgeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = KnowledgeRepository(db)
        self.embedder = get_embedder()
        self.store = get_vector_store()
        self.min_score = get_settings().rag_min_score

    # ---- documents ---------------------------------------------------------------------
    def list_documents(self, page: int, limit: int) -> tuple[list[KnowledgeDocument], int]:
        stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc())
        return self.repo.paginate(stmt, page, limit)

    def get(self, document_id: int) -> KnowledgeDocument:
        document = self.repo.get(document_id)
        if document is None:
            raise NotFoundError("Document", document_id)
        return document

    def ingest(self, data: DocumentCreate, user: User | None = None) -> KnowledgeDocument:
        digest = hashlib.sha256(data.content.encode()).hexdigest()
        if self.db.scalar(select(KnowledgeDocument).where(KnowledgeDocument.content_hash == digest)):
            raise ConflictError("This document has already been ingested")
        chunks = chunk_text(data.content)
        if not chunks:
            raise BusinessRuleError("The document contains no text")

        document = self.repo.add(
            KnowledgeDocument(
                title=data.title,
                source_name=data.source_name,
                content_hash=digest,
                chunk_count=len(chunks),
                char_count=len(data.content),
                uploaded_by=user.id if user else None,
            )
        )
        vectors = self.embedder.embed(chunks)
        self.store.ensure_collection(self.embedder.dim)
        self.store.upsert(
            [
                Point(
                    vector=vector,
                    payload={
                        "document_id": document.id,
                        "title": data.title,
                        "chunk_index": index,
                        "text": chunk,
                    },
                )
                for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
            ]
        )
        self.db.commit()  # vectors are written first: a failed upsert leaves no orphan DB row
        self.db.refresh(document)
        logger.info("document ingested id=%s chunks=%s", document.id, len(chunks))
        return document

    def delete(self, document_id: int) -> None:
        document = self.get(document_id)
        self.store.delete_document(document.id)
        self.repo.delete(document)
        self.db.commit()

    # ---- retrieval ---------------------------------------------------------------------
    def search(self, query: str, top_k: int = 5) -> list[Hit]:
        self.store.ensure_collection(self.embedder.dim)
        vector = self.embedder.embed([query])[0]
        return [h for h in self.store.search(vector, top_k) if h.score >= self.min_score]

    def ask(self, question: str, top_k: int = 4) -> dict:
        hits = self.search(question, top_k)
        if not hits:
            return {"question": question, "answer": NOT_FOUND, "citations": [], "grounded": False, "provider": "none"}

        llm = llm_module.get_llm()
        if llm is None:
            best = hits[0]
            snippet = " ".join(best.text.split())
            answer = f"From \"{best.title}\": {snippet[:450]}{'…' if len(snippet) > 450 else ''} [1]"
            provider = "extractive"
        else:
            context = "\n\n".join(f"[{i}] ({h.title}) {h.text}" for i, h in enumerate(hits, start=1))
            prompt = f"Context passages:\n{context}\n\nQuestion: {question}"
            answer = llm.generate(
                SYSTEM_PROMPT, [{"role": "user", "content": prompt}], max_tokens=600
            ).text.strip()
            provider = "llm"

        cited = sorted({int(n) for n in _CITATION.findall(answer) if 1 <= int(n) <= len(hits)})
        citations = [
            {
                "marker": n,
                "document_id": hits[n - 1].document_id,
                "title": hits[n - 1].title,
                "chunk_index": hits[n - 1].chunk_index,
                "snippet": " ".join(hits[n - 1].text.split())[:300],
                "score": round(hits[n - 1].score, 4),
            }
            for n in cited
        ]
        grounded = bool(citations) and answer != NOT_FOUND
        return {"question": question, "answer": answer, "citations": citations, "grounded": grounded, "provider": provider}

    # ---- evaluation --------------------------------------------------------------------
    def evaluate(self, request: EvaluateRequest) -> dict:
        cases = [EvalCase(c.question, c.expected_titles, c.expected_keywords) for c in request.cases]
        report = evaluate_retrieval(cases, lambda q, k: self.search(q, k), request.top_k)
        if request.with_answers:
            grounded = []
            for result in report["results"]:
                answer = self.ask(result["question"], request.top_k)
                result["grounded"] = answer["grounded"]
                grounded.append(answer["grounded"])
            report["grounded_rate"] = round(sum(grounded) / len(grounded), 4)
        return report
