"""Thin LLM abstraction so the assistant and RAG code are testable without network access."""

import logging
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    content: list[dict] = field(default_factory=list)  # assistant blocks, echoed back with tool results


class LLMClient(Protocol):
    def generate(
        self, system: str, messages: list[dict], tools: list[dict] | None = None, max_tokens: int = 1024
    ) -> LLMResponse: ...


class AnthropicLLM:
    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(api_key=api_key, timeout=30.0, max_retries=2)
        self.model = model

    def generate(
        self, system: str, messages: list[dict], tools: list[dict] | None = None, max_tokens: int = 1024
    ) -> LLMResponse:
        kwargs: dict = {"model": self.model, "max_tokens": max_tokens, "system": system, "messages": messages}
        if tools:
            kwargs["tools"] = tools
        try:
            response = self.client.messages.create(**kwargs)
        except self._anthropic.APIError as exc:
            logger.exception("LLM request failed")
            raise ExternalServiceError("The AI service is currently unavailable") from exc

        text_parts, calls, blocks = [], [], []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                blocks.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, input=dict(block.input)))
                blocks.append(
                    {"type": "tool_use", "id": block.id, "name": block.name, "input": dict(block.input)}
                )
        return LLMResponse(text="".join(text_parts), tool_calls=calls, content=blocks)


@lru_cache
def get_llm() -> LLMClient | None:
    """Returns None when no API key is configured; callers then use deterministic fallbacks."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    return AnthropicLLM(settings.anthropic_api_key, settings.anthropic_model)
