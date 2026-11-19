from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=200)
    content: str = Field(min_length=20, max_length=500_000)
    source_name: str | None = Field(default=None, max_length=255)


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source_name: str | None
    chunk_count: int
    char_count: int
    created_at: datetime


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)


class ChunkHit(BaseModel):
    document_id: int
    title: str
    chunk_index: int
    text: str
    score: float


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=10)


class Citation(BaseModel):
    marker: int
    document_id: int
    title: str
    chunk_index: int
    snippet: str
    score: float


class AskResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    grounded: bool = Field(description="True when the answer cites at least one retrieved passage")
    provider: str


class EvalCaseIn(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    expected_titles: list[str] = Field(default_factory=list)
    expected_keywords: list[str] = Field(default_factory=list)


class EvaluateRequest(BaseModel):
    cases: list[EvalCaseIn] = Field(min_length=1, max_length=100)
    top_k: int = Field(default=3, ge=1, le=10)
    with_answers: bool = False


class EvalCaseResult(BaseModel):
    question: str
    hit: bool
    first_relevant_rank: int | None
    reciprocal_rank: float
    precision_at_k: float
    top_titles: list[str]
    grounded: bool | None = None


class EvaluateResponse(BaseModel):
    cases: int
    top_k: int
    hit_rate: float
    mrr: float
    precision_at_k: float
    grounded_rate: float | None = None
    results: list[EvalCaseResult]
