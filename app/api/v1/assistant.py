from fastapi import APIRouter

from app.api.deps import AssistantSvc
from app.schemas.assistant import ChatRequest, ChatResponse

router = APIRouter(prefix="/assistant", tags=["AI Analytics Assistant"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, service: AssistantSvc):
    """Ask questions about procurement data in natural language.

    Uses Claude with tool-calling over the analytics endpoints when `ANTHROPIC_API_KEY` is set;
    otherwise a deterministic keyword fallback answers the same questions.
    """
    history = [m.model_dump() for m in payload.history]
    return service.chat(payload.message, history)
