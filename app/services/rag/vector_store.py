import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol


@dataclass
class Point:
    vector: list[float]
    payload: dict
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())


@dataclass
class Hit:
    document_id: int
    title: str
    chunk_index: int
    text: str
    score: float


class VectorStore(Protocol):
    def ensure_collection(self, dim: int) -> None: ...
    def upsert(self, points: list[Point]) -> None: ...
    def search(self, vector: list[float], top_k: int) -> list[Hit]: ...
    def delete_document(self, document_id: int) -> None: ...


def _to_hit(payload: dict, score: float) -> Hit:
    return Hit(
        document_id=int(payload["document_id"]),
        title=payload["title"],
        chunk_index=int(payload["chunk_index"]),
        text=payload["text"],
        score=float(score),
    )


class InMemoryStore:
    """Process-local cosine-similarity store used when QDRANT_URL is not set (dev and tests)."""

    def __init__(self) -> None:
        self._points: dict[str, Point] = {}

    def ensure_collection(self, dim: int) -> None:
        return None

    def upsert(self, points: list[Point]) -> None:
        for point in points:
            self._points[point.id] = point

    def search(self, vector: list[float], top_k: int) -> list[Hit]:
        scored = [
            (sum(a * b for a, b in zip(vector, p.vector, strict=False)), p)
            for p in self._points.values()
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [_to_hit(p.payload, score) for score, p in scored[:top_k]]

    def delete_document(self, document_id: int) -> None:
        self._points = {
            k: p for k, p in self._points.items() if p.payload["document_id"] != document_id
        }


class QdrantStore:
    def __init__(self, url: str, collection: str) -> None:
        from qdrant_client import QdrantClient

        self.client = QdrantClient(url=url, timeout=10)
        self.collection = collection
        self._ready = False

    def ensure_collection(self, dim: int) -> None:
        if self._ready:
            return
        from qdrant_client.models import Distance, VectorParams

        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection, vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
            )
        self._ready = True

    def upsert(self, points: list[Point]) -> None:
        from qdrant_client.models import PointStruct

        self.client.upsert(
            self.collection,
            points=[PointStruct(id=p.id, vector=p.vector, payload=p.payload) for p in points],
            wait=True,
        )

    def search(self, vector: list[float], top_k: int) -> list[Hit]:
        result = self.client.query_points(
            self.collection, query=vector, limit=top_k, with_payload=True
        )
        return [_to_hit(point.payload, point.score) for point in result.points]

    def delete_document(self, document_id: int) -> None:
        from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue

        self.client.delete(
            self.collection,
            points_selector=FilterSelector(
                filter=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))])
            ),
            wait=True,
        )


@lru_cache
def get_vector_store() -> VectorStore:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.qdrant_url:
        return QdrantStore(settings.qdrant_url, settings.qdrant_collection)
    return InMemoryStore()
