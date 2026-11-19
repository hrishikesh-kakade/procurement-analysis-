"""Text embedders. Standard library only for the default backend (no model download)."""

import hashlib
import math
import re
from collections import Counter
from functools import lru_cache
from typing import Protocol

_TOKEN = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an the of to in on for and or is are was were be been by with as at from that this it its "
    "can will must should may do does what which who when how any all per than then also".split()
)


def _stem(token: str) -> str:
    if len(token) > 5 and token.endswith("ing"):
        return token[:-3]
    if len(token) > 4 and token.endswith("ed"):
        return token[:-2]
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashingEmbedder:
    """Signed feature hashing of unigrams + bigrams (lexical similarity, deterministic, offline)."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        tokens = tokenize(text)
        features = Counter(tokens)
        bigrams = Counter(f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False))
        vector = [0.0] * self.dim
        for counts, weight in ((features, 1.0), (bigrams, 0.5)):
            for feature, count in counts.items():
                digest = int.from_bytes(hashlib.blake2b(feature.encode(), digest_size=8).digest(), "big")
                sign = 1.0 if (digest >> 63) & 1 else -1.0
                vector[digest % self.dim] += sign * weight * (1 + math.log(count))
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]


class FastEmbedEmbedder:
    """Semantic embeddings via fastembed (ONNX). Install requirements-ml.txt to use."""

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name=model_name)
        self.dim = len(next(iter(self._model.embed(["dimension probe"]))))

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in vector] for vector in self._model.embed(texts)]


@lru_cache
def get_embedder() -> Embedder:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.embedding_backend == "fastembed":
        return FastEmbedEmbedder(settings.embedding_model)
    return HashingEmbedder(settings.embedding_dim)
