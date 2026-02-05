"""LLM-based multi-query planner for retrieval (Milestone 4).

This module is optional: call sites should handle missing credentials/providers and
fallback to deterministic planning.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Protocol, Sequence, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from retrieval.query_planning.planner import generate_queries_for_question
from schemas.internal.locator import LocatorRules
from schemas.internal.rob2 import QuestionSet, Rob2Question
from utils.llm_json import extract_json_object

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


class ChatModelLike(Protocol):
    def with_structured_output(self, schema: type[BaseModel]) -> Any: ...
    def invoke(self, input: object) -> Any: ...


class _QueryPlanResponse(BaseModel):
    """Structured response expected from the LLM."""

    query_plan: Dict[str, List[str]] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


@dataclass(frozen=True)
class LLMQueryPlannerConfig:
    model: str
    model_provider: str | None = None
    temperature: float = 0.0
    timeout: float | None = None
    max_tokens: int | None = None
    max_retries: int | None = 2


def generate_query_plan_llm(
    question_set: QuestionSet,
    rules: LocatorRules,
    *,
    llm: ChatModelLike | None = None,
    config: LLMQueryPlannerConfig | None = None,
    max_queries_per_question: int = 5,
    max_keywords_per_question: int = 10,
) -> Dict[str, List[str]]:
    """Generate queries per question_id via LLM, merged with deterministic fallbacks."""
    if max_queries_per_question < 1:
        raise ValueError("max_queries_per_question must be >= 1")
    if max_keywords_per_question < 0:
        raise ValueError("max_keywords_per_question must be >= 0")

    deterministic = {
        question.question_id: generate_queries_for_question(
            question,
            rules,
            max_queries=max_queries_per_question,
        )
        for question in question_set.questions
    }
    if max_queries_per_question == 1:
        return deterministic

    model = llm
    if model is None:
        if config is None:
            raise ValueError("config is required when llm is not provided")
        model = _init_chat_model(config)

    response = _invoke_query_planner(
        model,
        question_set.questions,
        rules,
        max_queries=max_queries_per_question - 1,
        max_keywords=max_keywords_per_question,
    )

    llm_plan = _normalize_query_plan(
        response.query_plan,
        allowed_question_ids={question.question_id for question in question_set.questions},
    )

    merged: Dict[str, List[str]] = {}
    for question in question_set.questions:
        base = [question.text]
        llm_queries = llm_plan.get(question.question_id) or []
        deterministic_tail = [
            q for q in (deterministic.get(question.question_id) or []) if q != question.text
        ]
        merged[question.question_id] = _dedupe_preserve_order(
            _clean_query(q) for q in [*base, *llm_queries, *deterministic_tail]
        )[:max_queries_per_question]

    return merged


def _init_chat_model(config: LLMQueryPlannerConfig) -> ChatModelLike:
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


def _invoke_query_planner(
    llm: ChatModelLike,
    questions: Sequence[Rob2Question],
    rules: LocatorRules,
    *,
    max_queries: int,
    max_keywords: int,
) -> _QueryPlanResponse:
    payload = {
        "task": "Generate retrieval queries per ROB2 signaling question.",
        "constraints": {
            "max_queries_per_question": max_queries,
            "do_not_include_question_text": True,
            "no_explanations": True,
            "no_quotes": True,
            "plain_strings_only": True,
        },
        "questions": [
            _question_payload(question, rules, max_keywords=max_keywords)
            for question in questions
        ],
    }

    system_prompt = _load_query_planner_system_prompt(max_queries=max_queries)
    user_prompt = json.dumps(payload, ensure_ascii=False)

    messages = _build_messages(system_prompt, user_prompt)
    try:
        structured = llm.with_structured_output(_QueryPlanResponse)
        result = structured.invoke(messages)
        if isinstance(result, _QueryPlanResponse):
            return result
    except Exception:
        pass

    raw = llm.invoke(messages)
    content = getattr(raw, "content", raw)
    if not isinstance(content, str):
        content = str(content)
    return _parse_query_plan_response(content)


def _build_messages(system_prompt: str, user_prompt: str) -> "list[BaseMessage]":
    from langchain_core.messages import HumanMessage, SystemMessage

    return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]


def _question_payload(
    question: Rob2Question,
    rules: LocatorRules,
    *,
    max_keywords: int,
) -> dict[str, object]:
    override = rules.question_overrides.get(question.question_id)
    keyword_phrases = _merge_unique(
        override.keywords if override and override.keywords else [],
        rules.domains[question.domain].keywords,
    )
    if max_keywords:
        keyword_phrases = keyword_phrases[:max_keywords]
    else:
        keyword_phrases = []

    payload: dict[str, object] = {
        "question_id": question.question_id,
        "domain": question.domain,
        "text": question.text,
        "keyword_hints": keyword_phrases,
    }
    if question.effect_type:
        payload["effect_type"] = question.effect_type
    return payload


def _parse_query_plan_response(text: str) -> _QueryPlanResponse:
    extracted = _extract_json_object(text)
    try:
        payload = json.loads(extracted)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM query planner did not return valid JSON") from exc

    try:
        return _QueryPlanResponse.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("LLM query planner JSON did not match schema") from exc


def _extract_json_object(text: str) -> str:
    try:
        return extract_json_object(text, prefer_code_block=True)
    except ValueError as exc:
        raise ValueError("No JSON object found in LLM response") from exc


@lru_cache(maxsize=8)
def _load_query_planner_system_prompt(*, max_queries: int) -> str:
    prompt_path = (
        Path(__file__).resolve().parents[2]
        / "llm"
        / "prompts"
        / "planners"
        / "query_planner_system.md"
    )
    if prompt_path.exists():
        template = prompt_path.read_text(encoding="utf-8").strip()
    else:
        template = (
            "You generate short keyword-style search queries for retrieving evidence "
            "snippets from RCT papers. Return ONLY valid JSON matching this schema:\\n"
            "{\\n"
            '  \"query_plan\": {\\n'
            '    \"<question_id>\": [\"query 1\", \"query 2\", \"...\"]\\n'
            "  }\\n"
            "}\\n"
            "Rules:\\n"
            "- Provide at most {{max_queries}} queries per question_id.\\n"
            "- Do NOT include the full question text as a query.\\n"
            "- Use short phrases likely to appear in Methods/Results.\\n"
            "- Prefer methodology terms (randomization, allocation concealment, ITT, missing data, blinding).\\n"
            "- No commentary, no markdown, no code blocks."
        )
    return template.replace("{{max_queries}}", str(max_queries))


def _normalize_query_plan(
    query_plan: Mapping[str, object],
    *,
    allowed_question_ids: set[str],
) -> Dict[str, List[str]]:
    normalized: Dict[str, List[str]] = {}
    for key, value in query_plan.items():
        if not isinstance(key, str):
            continue
        question_id = key.strip()
        if not question_id or question_id not in allowed_question_ids:
            continue
        if not isinstance(value, list):
            continue
        queries: List[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            cleaned = _clean_query(item)
            if cleaned:
                queries.append(cleaned)
        normalized[question_id] = queries
    return normalized


def _clean_query(query: str) -> str:
    cleaned = " ".join(query.strip().split())
    cleaned = cleaned.strip("`\"'")
    return cleaned


def _merge_unique(a: Iterable[str], b: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    merged: List[str] = []
    for item in list(a) + list(b):
        cleaned = item.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(cleaned)
    return merged


def _dedupe_preserve_order(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


__all__ = ["LLMQueryPlannerConfig", "generate_query_plan_llm"]
