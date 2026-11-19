import math

from app.core.embeddings import HashingEmbedder, tokenize
from app.services.rag.chunking import chunk_text
from app.services.rag.evaluation import EvalCase, evaluate_retrieval, is_relevant
from app.services.rag.vector_store import Hit, InMemoryStore, Point


def test_chunker_keeps_short_text_in_one_chunk():
    assert chunk_text("Short paragraph about purchasing rules.") == ["Short paragraph about purchasing rules."]
    assert chunk_text("   \n\n  ") == []


def test_chunker_respects_max_size_and_overlaps():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 60 for i in range(8))
    chunks = chunk_text(text, max_chars=500, overlap_chars=50)
    assert len(chunks) > 1
    assert all(len(c) <= 500 + 60 for c in chunks)
    assert chunks[0][-30:] in chunks[1]  # overlap carries context across chunks


def test_chunker_attaches_headings_to_following_paragraph():
    chunks = chunk_text("# Title\n\nBody text that follows the heading.")
    assert chunks == ["# Title\nBody text that follows the heading."]


def test_chunker_splits_oversized_paragraph_on_sentences():
    long_paragraph = " ".join(f"Sentence number {i} is here." for i in range(80))
    chunks = chunk_text(long_paragraph, max_chars=300, overlap_chars=0)
    assert len(chunks) > 3 and all(len(c) <= 300 for c in chunks)


def test_tokenizer_drops_stopwords_and_stems():
    assert tokenize("The approvals are required") == ["approval", "requir"]


def test_embedder_is_deterministic_and_normalised():
    embedder = HashingEmbedder(dim=128)
    a, b = embedder.embed(["supplier scorecard rating"])[0], embedder.embed(["supplier scorecard rating"])[0]
    assert a == b and len(a) == 128
    assert math.isclose(sum(x * x for x in a), 1.0, rel_tol=1e-9)


def test_embedder_ranks_related_text_higher():
    embedder = HashingEmbedder()
    query, related, unrelated = embedder.embed(
        ["requisition approval limits", "requisitions above the limit need approval", "pallet wrap roll storage"]
    )
    dot = lambda x, y: sum(p * q for p, q in zip(x, y, strict=True))  # noqa: E731
    assert dot(query, related) > dot(query, unrelated)


def test_in_memory_store_search_and_delete():
    store = InMemoryStore()
    store.upsert(
        [
            Point([1.0, 0.0], {"document_id": 1, "title": "A", "chunk_index": 0, "text": "alpha"}),
            Point([0.0, 1.0], {"document_id": 2, "title": "B", "chunk_index": 0, "text": "beta"}),
        ]
    )
    hits = store.search([0.9, 0.1], top_k=2)
    assert [h.title for h in hits] == ["A", "B"] and hits[0].score > hits[1].score
    store.delete_document(1)
    assert [h.title for h in store.search([1.0, 0.0], top_k=5)] == ["B"]


def test_evaluation_metrics():
    def hit(title, text="text"):
        return Hit(document_id=1, title=title, chunk_index=0, text=text, score=1.0)

    corpus = {"q1": [hit("Wrong"), hit("Right")], "q2": [hit("Nope"), hit("Nada")], "q3": [hit("Right")]}
    cases = [EvalCase("q1", ["Right"]), EvalCase("q2", ["Right"]), EvalCase("q3", ["Right"])]
    report = evaluate_retrieval(cases, lambda q, k: corpus[q][:k], top_k=2)
    assert report["hit_rate"] == round(2 / 3, 4)
    assert report["mrr"] == round((0.5 + 0 + 1) / 3, 4)
    assert [r["first_relevant_rank"] for r in report["results"]] == [2, None, 1]


def test_keyword_relevance_requires_all_keywords():
    chunk = Hit(1, "Doc", 0, "Three active suppliers must quote", 1.0)
    assert is_relevant(chunk, EvalCase("q", expected_keywords=["three", "suppliers"]))
    assert not is_relevant(chunk, EvalCase("q", expected_keywords=["three", "banana"]))
