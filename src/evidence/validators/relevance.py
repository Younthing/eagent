"""Relevance validation for evidence candidates (Milestone 7).

This module annotates fused evidence candidates with an LLM-based relevance
judgement. Callers should treat it as optional and handle missing credentials
or provider errors gracefully.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, List, Literal, Protocol, Sequence, TYPE_CHECKING, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from schemas.internal.evidence import (
    FusedEvidenceCandidate,
    RelevanceVerdict,
)

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


class ChatModelLike(Protocol):
    def with_structured_output(self, schema: type[BaseModel]) -> Any: ...
    def invoke(self, input: object) -> Any: ...


class _RelevanceResponse(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    supporting_quote: str | None = None

    model_config = ConfigDict(extra="ignore")


@dataclass(frozen=True)
class LLMRelevanceValidatorConfig:
    model: str
    model_provider: str | None = None
    temperature: float = 0.0
    timeout: float | None = None
    max_tokens: int | None = None
    max_retries: int | None = 2


@dataclass(frozen=True)
class RelevanceValidationConfig:
    min_confidence: float = 0.6
    require_supporting_quote: bool = True


_CODE_BLOCK_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def annotate_relevance(
    question_text: str,
    candidates: Sequence[FusedEvidenceCandidate],
    *,
    llm: ChatModelLike | None = None,
    llm_config: LLMRelevanceValidatorConfig | None = None,
    config: RelevanceValidationConfig | None = None,
) -> List[FusedEvidenceCandidate]:
    """Annotate candidates with relevance verdicts (LLM-based when available)."""
    validation_config = config or RelevanceValidationConfig()
    if validation_config.min_confidence < 0 or validation_config.min_confidence > 1:
        raise ValueError("min_confidence must be between 0 and 1")

    model = llm
    if model is None and llm_config is not None:
        model = _init_chat_model(llm_config)

    annotated: List[FusedEvidenceCandidate] = []
    for candidate in candidates:
        verdict = RelevanceVerdict(label="unknown", confidence=None, supporting_quote=None)
        if model is not None:
            try:
                verdict = _judge_relevance(
                    model,
                    question_text=question_text,
                    candidate=candidate,
                    require_quote=validation_config.require_supporting_quote,
                )
            except Exception:
                verdict = RelevanceVerdict(label="unknown", confidence=None, supporting_quote=None)

        annotated.append(
            candidate.model_copy(update={"relevance": verdict})
        )

    return annotated


def _init_chat_model(config: LLMRelevanceValidatorConfig) -> ChatModelLike:
    from langchain.chat_models import init_chat_model

    kwargs: dict[str, Any] = {}
    if config.model_provider:
        kwargs["model_provider"] = config.model_provider
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    if config.timeout is not None:
        kwargs["timeout"] = config.timeout
    if config.max_tokens is not None:
        kwargs["max_tokens"] = config.max_tokens
    if config.max_retries is not None:
        kwargs["max_retries"] = config.max_retries

    return init_chat_model(config.model, **kwargs)


def _judge_relevance(
    llm: ChatModelLike,
    *,
    question_text: str,
    candidate: FusedEvidenceCandidate,
    require_quote: bool,
) -> RelevanceVerdict:
    system_prompt = (
        "You judge whether a paragraph contains DIRECT evidence to answer a ROB2 signaling question.\n"
        "Return ONLY valid JSON with keys: label, confidence, supporting_quote.\n"
        "label must be one of: relevant, irrelevant, unknown.\n"
        "confidence must be a number between 0 and 1.\n"
        "supporting_quote must be an EXACT substring copied from the paragraph, or null.\n"
        "If the paragraph does not contain an explicit statement answering the question, choose irrelevant.\n"
        "If you are unsure, choose unknown.\n"
        "No markdown, no explanations."
    )

    payload = {
        "question": question_text,
        "paragraph": {
            "paragraph_id": candidate.paragraph_id,
            "title": candidate.title,
            "page": candidate.page,
            "text": candidate.text,
        },
    }
    user_prompt = json.dumps(payload, ensure_ascii=False)
    messages = _build_messages(system_prompt, user_prompt)

    try:
        structured = llm.with_structured_output(_RelevanceResponse)
        result = structured.invoke(messages)
        if isinstance(result, _RelevanceResponse):
            return _normalize_verdict(result, candidate.text, require_quote=require_quote)
    except Exception:
        pass

    raw = llm.invoke(messages)
    content = getattr(raw, "content", raw)
    if not isinstance(content, str):
        content = str(content)

    response = _parse_relevance_response(content)
    return _normalize_verdict(response, candidate.text, require_quote=require_quote)


def _build_messages(system_prompt: str, user_prompt: str) -> "list[BaseMessage]":
    from langchain_core.messages import HumanMessage, SystemMessage

    return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]


def _parse_relevance_response(text: str) -> _RelevanceResponse:
    extracted = _extract_json_object(text)
    try:
        payload = json.loads(extracted)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM relevance validator did not return valid JSON") from exc

    try:
        return _RelevanceResponse.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("LLM relevance validator JSON did not match schema") from exc


def _extract_json_object(text: str) -> str:
    match = _CODE_BLOCK_JSON.search(text)
    if match:
        return match.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response")
    return text[start : end + 1]


def _normalize_verdict(
    response: _RelevanceResponse,
    paragraph_text: str,
    *,
    require_quote: bool,
) -> RelevanceVerdict:
    label = str(response.label or "").strip().lower()
    if label not in {"relevant", "irrelevant", "unknown"}:
        label = "unknown"
    label_value = cast(Literal["relevant", "irrelevant", "unknown"], label)

    confidence = float(response.confidence)
    if label_value == "unknown":
        confidence_value: float | None = None
    else:
        confidence_value = max(0.0, min(1.0, confidence))

    quote = response.supporting_quote
    if quote is not None:
        quote = " ".join(str(quote).split())
        if not quote:
            quote = None

    if require_quote and label_value == "relevant":
        if quote is None or quote not in paragraph_text:
            return RelevanceVerdict(label="unknown", confidence=None, supporting_quote=None)

    return RelevanceVerdict(
        label=label_value,
        confidence=confidence_value,
        supporting_quote=quote,
    )


__all__ = [
    "ChatModelLike",
    "LLMRelevanceValidatorConfig",
    "RelevanceValidationConfig",
    "annotate_relevance",
]
