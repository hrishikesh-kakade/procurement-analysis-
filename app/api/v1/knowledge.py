from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import KnowledgeSvc, Pagination
from app.api.permissions import MANAGE, CurrentUser
from app.core.exceptions import BusinessRuleError
from app.schemas.common import Page, build_page
from app.schemas.knowledge import (
    AskRequest,
    AskResponse,
    ChunkHit,
    DocumentCreate,
    DocumentRead,
    EvaluateRequest,
    EvaluateResponse,
    SearchRequest,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base (RAG)"])
MAX_UPLOAD_BYTES = 1_000_000


@router.post("/documents", dependencies=MANAGE, response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
def add_document(payload: DocumentCreate, service: KnowledgeSvc, user: CurrentUser):
    """Chunk, embed and index a policy document."""
    return service.ingest(payload, user)


@router.post(
    "/documents/upload",
    dependencies=MANAGE,
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a .txt or .md file",
)
def upload_document(
    service: KnowledgeSvc,
    user: CurrentUser,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
):
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise BusinessRuleError("File is too large (limit 1 MB)")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BusinessRuleError("Only UTF-8 text files (.txt, .md) are supported") from exc
    name = file.filename or "document"
    payload = DocumentCreate(title=title or name.rsplit(".", 1)[0], content=content, source_name=name)
    return service.ingest(payload, user)


@router.get("/documents", response_model=Page[DocumentRead])
def list_documents(service: KnowledgeSvc, pagination: Pagination):
    items, total = service.list_documents(pagination.page, pagination.limit)
    return build_page(items, total, pagination)


@router.delete("/documents/{document_id}", dependencies=MANAGE, status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, service: KnowledgeSvc):
    service.delete(document_id)


@router.post("/search", response_model=list[ChunkHit], summary="Semantic search")
def search(payload: SearchRequest, service: KnowledgeSvc):
    return [h.__dict__ for h in service.search(payload.query, payload.top_k)]


@router.post("/ask", response_model=AskResponse, summary="Answer with citations")
def ask(payload: AskRequest, service: KnowledgeSvc):
    """Retrieval-augmented answer. Every claim must cite a numbered passage; see `grounded`."""
    return service.ask(payload.question, payload.top_k)


@router.post("/evaluate", dependencies=MANAGE, response_model=EvaluateResponse, summary="Evaluate retrieval quality")
def evaluate(payload: EvaluateRequest, service: KnowledgeSvc):
    """Hit-rate@k, MRR and precision@k for labelled questions (optionally answer grounding)."""
    return service.evaluate(payload)
