"""Consistency validation across evidence candidates (Milestone 7).

This validator checks whether multiple candidate paragraphs for the same
question contradict each other. The initial implementation is LLM-based and
optional; callers should handle missing credentials/providers gracefully.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Literal, Protocol, Sequence, TYPE_CHECKING, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from schemas.internal.evidence import (
    ConsistencyConflict,
    ConsistencyVerdict,
    FusedEvidenceCandidate,
)
from utils.llm_json import extract_json_object

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


class ChatModelLike(Protocol):
    def with_structured_output(self, schema: type[BaseModel]) -> Any: ...
    def invoke(self, input: object) -> Any: ...


class _Conflict(BaseModel):
    paragraph_id_a: str
    paragraph_id_b: str
    reason: str | None = None
    quote_a: str | None = None
    quote_b: str | None = None

    model_config = ConfigDict(extra="ignore")


class _ConsistencyResponse(BaseModel):
    label: str
    confidence: float = Field(ge=0, le=1)
    conflicts: List[_Conflict] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


@dataclass(frozen=True)
class LLMConsistencyValidatorConfig:
    model: str
    model_provider: str | None = None
    temperature: float = 0.0
    timeout: float | None = None
    max_tokens: int | None = None
    max_retries: int | None = 2


@dataclass(frozen=True)
class ConsistencyValidationConfig:
    min_confidence: float = 0.6
    require_quotes_for_fail: bool = True


def judge_consistency(
    question_text: str,
    candidates: Sequence[FusedEvidenceCandidate],
    *,
    llm: ChatModelLike | None = None,
    llm_config: LLMConsistencyValidatorConfig | None = None,
    config: ConsistencyValidationConfig | None = None,
) -> ConsistencyVerdict:
    """Return a consistency verdict for a set of candidates."""
    cfg = config or ConsistencyValidationConfig()
    if cfg.min_confidence < 0 or cfg.min_confidence > 1:
        raise ValueError("min_confidence must be between 0 and 1")

    if len(candidates) < 2:
        return ConsistencyVerdict(
            label="pass" if candidates else "unknown",
            confidence=None,
            conflicts=[],
        )

    model = llm
    if model is None and llm_config is not None:
        model = _init_chat_model(llm_config)
    if model is None:
        return ConsistencyVerdict(label="unknown", confidence=None, conflicts=[])

    try:
        response = _invoke_consistency(model, question_text, candidates)
    except Exception:
        return ConsistencyVerdict(label="unknown", confidence=None, conflicts=[])

    return _normalize_verdict(response, candidates, cfg)


def _init_chat_model(config: LLMConsistencyValidatorConfig) -> ChatModelLike:
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


def _invoke_consistency(
    llm: ChatModelLike,
    question_text: str,
    candidates: Sequence[FusedEvidenceCandidate],
) -> _ConsistencyResponse:
    payload = {
        "question": question_text,
        "paragraphs": [
            {
                "paragraph_id": candidate.paragraph_id,
                "title": candidate.title,
                "page": candidate.page,
                "text": candidate.text,
                "supporting_quote": candidate.relevance.supporting_quote
                if candidate.relevance is not None
                else None,
            }
            for candidate in candidates
        ],
    }

    system_prompt = _load_consistency_system_prompt()
    user_prompt = json.dumps(payload, ensure_ascii=False)
    messages = _build_messages(system_prompt, user_prompt)

    try:
        structured = llm.with_structured_output(_ConsistencyResponse)
        result = structured.invoke(messages)
        if isinstance(result, _ConsistencyResponse):
            return result
    except Exception:
        pass

    raw = llm.invoke(messages)
    content = getattr(raw, "content", raw)
    if not isinstance(content, str):
        content = str(content)
    return _parse_consistency_response(content)


def _build_messages(system_prompt: str, user_prompt: str) -> "list[BaseMessage]":
    from langchain_core.messages import HumanMessage, SystemMessage

    return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]


def _parse_consistency_response(text: str) -> _ConsistencyResponse:
    extracted = _extract_json_object(text)
    try:
        payload = json.loads(extracted)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM consistency validator did not return valid JSON") from exc

    try:
        return _ConsistencyResponse.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("LLM consistency validator JSON did not match schema") from exc


def _extract_json_object(text: str) -> str:
    try:
        return extract_json_object(text, prefer_code_block=True)
    except ValueError as exc:
        raise ValueError("No JSON object found in LLM response") from exc


@lru_cache(maxsize=1)
def _load_consistency_system_prompt() -> str:
    prompt_path = (
        Path(__file__).resolve().parents[2]
        / "llm"
        / "prompts"
        / "validators"
        / "consistency_system.md"
    )
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return (
        "You check whether multiple paragraphs contradict each other about a ROB2 signaling question.\n"
        "Return ONLY JSON with keys: label, confidence, conflicts.\n"
        "label must be one of: pass, fail, unknown.\n"
        "conflicts is a list of objects: paragraph_id_a, paragraph_id_b, reason, quote_a, quote_b.\n"
        "If you mark fail, include at least one conflict and provide quote_a/quote_b as exact substrings.\n"
        "No markdown, no explanations."
    )


def _normalize_verdict(
    response: _ConsistencyResponse,
    candidates: Sequence[FusedEvidenceCandidate],
    cfg: ConsistencyValidationConfig,
) -> ConsistencyVerdict:
    label_raw = str(response.label or "").strip().lower()
    if label_raw not in {"pass", "fail", "unknown"}:
        label_raw = "unknown"
    label = cast(Literal["pass", "fail", "unknown"], label_raw)

    confidence_value: float | None
    if label == "unknown":
        confidence_value = None
    else:
        confidence_value = max(0.0, min(1.0, float(response.confidence)))

    text_by_pid = {candidate.paragraph_id: candidate.text for candidate in candidates}
    conflicts: List[ConsistencyConflict] = []
    for conflict in response.conflicts or []:
        pid_a = str(conflict.paragraph_id_a).strip()
        pid_b = str(conflict.paragraph_id_b).strip()
        if not pid_a or not pid_b or pid_a == pid_b:
            continue
        if pid_a not in text_by_pid or pid_b not in text_by_pid:
            continue
        quote_a = conflict.quote_a
        quote_b = conflict.quote_b
        if quote_a is not None and quote_a not in text_by_pid[pid_a]:
            quote_a = None
        if quote_b is not None and quote_b not in text_by_pid[pid_b]:
            quote_b = None
        conflicts.append(
            ConsistencyConflict(
                paragraph_id_a=pid_a,
                paragraph_id_b=pid_b,
                reason=conflict.reason,
                quote_a=quote_a,
                quote_b=quote_b,
            )
        )

    if label == "fail":
        if confidence_value is None or confidence_value < cfg.min_confidence:
            return ConsistencyVerdict(label="unknown", confidence=None, conflicts=[])
        if not conflicts:
            return ConsistencyVerdict(label="unknown", confidence=None, conflicts=[])
        if cfg.require_quotes_for_fail and any(
            conflict.quote_a is None or conflict.quote_b is None for conflict in conflicts
        ):
            return ConsistencyVerdict(label="unknown", confidence=None, conflicts=[])

    if label == "pass":
        return ConsistencyVerdict(label="pass", confidence=confidence_value, conflicts=[])

    if label == "unknown":
        return ConsistencyVerdict(label="unknown", confidence=None, conflicts=[])

    return ConsistencyVerdict(label="fail", confidence=confidence_value, conflicts=conflicts)


__all__ = [
    "ChatModelLike",
    "ConsistencyValidationConfig",
    "LLMConsistencyValidatorConfig",
    "judge_consistency",
]
