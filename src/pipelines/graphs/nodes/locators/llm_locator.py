"""LLM-driven evidence locator with iterative expansion (ReAct-style)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from retrieval.engines.bm25 import BM25Index, build_bm25_index
from retrieval.structure.section_prior import normalize_for_match, score_section_title
from retrieval.tokenization import resolve_tokenizer_config
from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.evidence import EvidenceCandidate
from schemas.internal.rob2 import QuestionSet, Rob2Question
from pipelines.graphs.nodes.retry_utils import (
    filter_question_set,
    merge_by_question,
    read_retry_question_ids,
)
from utils.llm_json import extract_json_object

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


class ChatModelLike(Protocol):
    def with_structured_output(self, schema: type[BaseModel]) -> Any: ...

    def invoke(self, input: object) -> Any: ...


class _LocatorEvidence(BaseModel):
    paragraph_id: str | None = None
    quote: str | None = None

    model_config = ConfigDict(extra="ignore")


class _LocatorExpand(BaseModel):
    keywords: List[str] = Field(default_factory=list)
    section_priors: List[str] = Field(default_factory=list)
    queries: List[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class _LocatorResponse(BaseModel):
    sufficient: bool = False
    evidence: List[_LocatorEvidence] = Field(default_factory=list)
    expand: Optional[_LocatorExpand] = None

    model_config = ConfigDict(extra="ignore")


@dataclass(frozen=True)
class LLMLocatorConfig:
    model: str
    model_provider: str | None = None
    temperature: float = 0.0
    timeout: float | None = None
    max_tokens: int | None = None
    max_retries: int | None = 2


@dataclass
class _CandidateInfo:
    span: SectionSpan
    score: float
    source: str


_DEFAULT_MAX_STEPS = 3
_DEFAULT_SEED_TOP_N = 5
_DEFAULT_PER_STEP_TOP_N = 10
_DEFAULT_MAX_CANDIDATES = 40


@lru_cache(maxsize=1)
def _load_system_prompt() -> str:
    prompt_path = (
        Path(__file__).resolve().parents[4]
        / "llm"
        / "prompts"
        / "locators"
        / "llm_locator_system.md"
    )
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return (
        "You are a ROB2 evidence locator. You receive a question and candidate paragraphs.\n"
        "Return ONLY valid JSON with keys: sufficient, evidence, expand.\n"
        "evidence items must include paragraph_id and an exact quote from that paragraph.\n"
        "If evidence is insufficient, set sufficient=false and propose expand keywords, section_priors, and queries.\n"
        "Use only the provided candidate paragraphs for evidence citations."
    )


def llm_locator_node(state: dict) -> dict:
    """LangGraph node: locate evidence via LLM-guided iterative expansion."""
    raw_doc = state.get("doc_structure")
    raw_questions = state.get("question_set")
    if raw_doc is None:
        raise ValueError("llm_locator_node requires 'doc_structure'.")
    if raw_questions is None:
        raise ValueError("llm_locator_node requires 'question_set'.")

    doc_structure = DocStructure.model_validate(raw_doc)
    question_set = QuestionSet.model_validate(raw_questions)

    mode = str(state.get("llm_locator_mode") or "none").strip().lower()
    if mode not in {"llm", "none"}:
        raise ValueError("llm_locator_mode must be 'llm' or 'none'")
    if mode == "none":
        return {"fulltext_candidates": {}, "llm_locator_debug": {}}

    retry_ids = read_retry_question_ids(state)
    target_questions = filter_question_set(question_set, retry_ids)

    llm = state.get("llm_locator_llm")
    used = mode
    error: str | None = None
    model_id = str(state.get("llm_locator_model") or "").strip()
    model_provider = state.get("llm_locator_model_provider")
    temperature_raw = state.get("llm_locator_temperature")
    temperature = 0.0 if temperature_raw is None else float(str(temperature_raw))
    timeout_raw = state.get("llm_locator_timeout")
    timeout = None if timeout_raw is None else float(str(timeout_raw))
    max_tokens_raw = state.get("llm_locator_max_tokens")
    max_tokens = None if max_tokens_raw is None else int(str(max_tokens_raw))
    max_retries_raw = state.get("llm_locator_max_retries")
    max_retries = 2 if max_retries_raw is None else int(str(max_retries_raw))

    llm_config: LLMLocatorConfig | None = None
    if llm is None:
        if not model_id:
            used = "none"
            error = (
                "Missing LLM locator model (set LLM_LOCATOR_MODEL or state['llm_locator_model'])."
            )
        else:
            llm_config = LLMLocatorConfig(
                model=model_id,
                model_provider=str(model_provider) if model_provider else None,
                temperature=temperature,
                timeout=timeout,
                max_tokens=max_tokens,
                max_retries=max_retries,
            )
            llm = _init_chat_model(llm_config)

    if llm is None:
        return {"llm_locator_debug": {"error": error, "used": used}}

    max_steps = int(state.get("llm_locator_max_steps") or _DEFAULT_MAX_STEPS)
    if max_steps < 1:
        raise ValueError("llm_locator_max_steps must be >= 1")

    seed_top_n = int(state.get("llm_locator_seed_top_n") or _DEFAULT_SEED_TOP_N)
    per_step_top_n = int(
        state.get("llm_locator_per_step_top_n") or _DEFAULT_PER_STEP_TOP_N
    )
    max_candidates = int(
        state.get("llm_locator_max_candidates") or _DEFAULT_MAX_CANDIDATES
    )
    if seed_top_n < 1 or per_step_top_n < 1 or max_candidates < 1:
        raise ValueError("llm_locator_*_top_n/max_candidates must be >= 1")

    spans = doc_structure.sections
    spans_by_pid = {span.paragraph_id: span for span in spans}
    tokenizer_config = resolve_tokenizer_config(
        state.get("locator_tokenizer"), state.get("locator_char_ngram")
    )
    bm25_index = build_bm25_index(spans, tokenizer=tokenizer_config)

    candidates_by_q: Dict[str, List[dict]] = {}
    debug: Dict[str, dict] = {}
    question_text_by_id = {
        question.question_id: question.text for question in question_set.questions
    }

    for question in target_questions.questions:
        question_id = question.question_id
        pool: Dict[str, _CandidateInfo] = {}
        _seed_pool(pool, spans_by_pid, state, question_id, seed_top_n)

        evidence_pool: List[EvidenceCandidate] = []
        debug_steps: List[dict] = []

        for step in range(max_steps):
            candidate_spans = _select_top_spans(pool, max_candidates)
            allowed_ids = {span.paragraph_id for span in candidate_spans}
            payload = _build_payload(
                question=question,
                question_text=question_text_by_id.get(question_id) or question.text,
                spans=candidate_spans,
                step=step + 1,
                max_steps=max_steps,
            )
            try:
                response = _invoke_locator(llm, payload)
            except Exception as exc:
                debug_steps.append(
                    {"step": step + 1, "error": f"{type(exc).__name__}: {exc}"}
                )
                break

            step_info = {
                "step": step + 1,
                "sufficient": bool(response.sufficient),
                "evidence_requested": len(response.evidence),
            }

            valid, invalid = _collect_evidence(
                response.evidence, spans_by_pid, question_id, allowed_ids
            )
            step_info["evidence_valid"] = len(valid)
            step_info["evidence_invalid"] = invalid
            _merge_evidence_pool(evidence_pool, valid)

            expand = response.expand or _LocatorExpand()
            clean_expand = {
                "keywords": _clean_list(expand.keywords),
                "section_priors": _clean_list(expand.section_priors),
                "queries": _clean_list(expand.queries),
            }
            step_info["expand"] = clean_expand
            debug_steps.append(step_info)

            if response.sufficient:
                break

            if step >= max_steps - 1:
                break

            _expand_pool(
                pool,
                spans=spans,
                bm25_index=bm25_index,
                keywords=clean_expand["keywords"],
                section_priors=clean_expand["section_priors"],
                queries=clean_expand["queries"],
                per_step_top_n=per_step_top_n,
                max_candidates=max_candidates,
            )

        candidates_by_q[question_id] = [candidate.model_dump() for candidate in evidence_pool]
        debug[question_id] = {
            "steps": debug_steps,
            "seed_top_n": seed_top_n,
            "per_step_top_n": per_step_top_n,
            "max_candidates": max_candidates,
            "used": used,
            "error": error,
        }

    if retry_ids:
        candidates_by_q = merge_by_question(
            state.get("fulltext_candidates"), candidates_by_q, retry_ids
        )
        debug = merge_by_question(state.get("llm_locator_debug"), debug, retry_ids)

    return {"fulltext_candidates": candidates_by_q, "llm_locator_debug": debug}


def _init_chat_model(config: LLMLocatorConfig) -> ChatModelLike:
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


def _build_payload(
    *,
    question: Rob2Question,
    question_text: str,
    spans: Sequence[SectionSpan],
    step: int,
    max_steps: int,
) -> dict[str, object]:
    question_payload: dict[str, object] = {
        "question_id": question.question_id,
        "domain": question.domain,
        "text": question_text,
    }
    if question.effect_type:
        question_payload["effect_type"] = question.effect_type

    payload: dict[str, object] = {
        "question": question_payload,
        "step": step,
        "max_steps": max_steps,
        "candidates": [
            {
                "paragraph_id": span.paragraph_id,
                "title": span.title,
                "page": span.page,
                "text": span.text,
            }
            for span in spans
        ],
    }
    return payload


def _invoke_locator(llm: ChatModelLike, payload: dict[str, object]) -> _LocatorResponse:
    system_prompt = _load_system_prompt()
    user_prompt = json.dumps(payload, ensure_ascii=False)
    messages = _build_messages(system_prompt, user_prompt)
    try:
        structured = llm.with_structured_output(_LocatorResponse)
        result = structured.invoke(messages)
        if isinstance(result, _LocatorResponse):
            return result
    except Exception:
        pass

    raw = llm.invoke(messages)
    content = getattr(raw, "content", raw)
    if not isinstance(content, str):
        content = str(content)
    return _parse_locator_response(content)


def _build_messages(system_prompt: str, user_prompt: str) -> "list[BaseMessage]":
    from langchain_core.messages import HumanMessage, SystemMessage

    return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]


def _parse_locator_response(text: str) -> _LocatorResponse:
    extracted = _extract_json_object(text)
    try:
        payload = json.loads(extracted)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM locator did not return valid JSON") from exc

    try:
        return _LocatorResponse.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("LLM locator JSON did not match schema") from exc


def _extract_json_object(text: str) -> str:
    try:
        return extract_json_object(text, prefer_code_block=True)
    except ValueError as exc:
        raise ValueError("No JSON object found in LLM response") from exc


def _clean_list(values: Sequence[str] | None) -> List[str]:
    cleaned: List[str] = []
    seen: set[str] = set()
    for value in values or []:
        if not isinstance(value, str):
            continue
        item = value.strip()
        if not item:
            continue
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    return cleaned


def _seed_pool(
    pool: Dict[str, _CandidateInfo],
    spans_by_pid: Mapping[str, SectionSpan],
    state: Mapping[str, Any],
    question_id: str,
    seed_top_n: int,
) -> None:
    _seed_from_map(pool, spans_by_pid, state.get("rule_based_candidates"), question_id, seed_top_n, "rule_based")
    _seed_from_map(pool, spans_by_pid, state.get("bm25_candidates"), question_id, seed_top_n, "bm25")
    _seed_from_map(pool, spans_by_pid, state.get("splade_candidates"), question_id, seed_top_n, "splade")


def _seed_from_map(
    pool: Dict[str, _CandidateInfo],
    spans_by_pid: Mapping[str, SectionSpan],
    raw_map: Any,
    question_id: str,
    seed_top_n: int,
    source: str,
) -> None:
    if not isinstance(raw_map, Mapping):
        return
    raw_list = raw_map.get(question_id)
    if not isinstance(raw_list, list):
        return
    for raw in raw_list[:seed_top_n]:
        try:
            candidate = EvidenceCandidate.model_validate(raw)
        except Exception:
            continue
        span = spans_by_pid.get(candidate.paragraph_id)
        if span is None:
            continue
        _add_candidate(pool, span, float(candidate.score), f"seed:{source}")


def _add_candidate(
    pool: Dict[str, _CandidateInfo],
    span: SectionSpan,
    score: float,
    source: str,
) -> None:
    pid = span.paragraph_id
    existing = pool.get(pid)
    if existing is None or score > existing.score:
        pool[pid] = _CandidateInfo(span=span, score=score, source=source)


def _select_top_spans(
    pool: Mapping[str, _CandidateInfo],
    max_candidates: int,
) -> List[SectionSpan]:
    ranked = sorted(
        pool.values(),
        key=lambda item: (-item.score, item.span.paragraph_id),
    )
    selected = ranked[:max_candidates]
    return [item.span for item in selected]


def _collect_evidence(
    evidence: Sequence[_LocatorEvidence],
    spans_by_pid: Mapping[str, SectionSpan],
    question_id: str,
    allowed_ids: set[str],
) -> Tuple[List[EvidenceCandidate], List[dict]]:
    valid: List[EvidenceCandidate] = []
    invalid: List[dict] = []

    for item in evidence:
        paragraph_id = (item.paragraph_id or "").strip()
        quote = item.quote
        quote = quote.strip() if isinstance(quote, str) else ""
        if not paragraph_id or not quote:
            invalid.append(
                {
                    "paragraph_id": paragraph_id or None,
                    "quote": quote or None,
                    "reason": "missing_fields",
                }
            )
            continue

        if paragraph_id not in allowed_ids:
            invalid.append(
                {
                    "paragraph_id": paragraph_id,
                    "quote": quote,
                    "reason": "paragraph_not_in_candidates",
                }
            )
            continue

        span = spans_by_pid.get(paragraph_id)
        if span is None:
            invalid.append(
                {
                    "paragraph_id": paragraph_id,
                    "quote": quote,
                    "reason": "paragraph_not_found",
                }
            )
            continue
        if quote not in (span.text or ""):
            invalid.append(
                {
                    "paragraph_id": paragraph_id,
                    "quote": quote,
                    "reason": "quote_not_found",
                }
            )
            continue

        valid.append(
            EvidenceCandidate(
                question_id=question_id,
                paragraph_id=paragraph_id,
                title=span.title,
                page=span.page,
                text=span.text,
                source="fulltext",
                score=1.0,
                engine="llm_locator",
                supporting_quote=quote,
            )
        )

    return valid, invalid


def _merge_evidence_pool(
    pool: List[EvidenceCandidate],
    new_items: Sequence[EvidenceCandidate],
) -> None:
    seen = {(item.paragraph_id, item.supporting_quote) for item in pool}
    for item in new_items:
        key = (item.paragraph_id, item.supporting_quote)
        if key in seen:
            continue
        seen.add(key)
        pool.append(item)


def _expand_pool(
    pool: Dict[str, _CandidateInfo],
    *,
    spans: Sequence[SectionSpan],
    bm25_index: BM25Index,
    keywords: Sequence[str],
    section_priors: Sequence[str],
    queries: Sequence[str],
    per_step_top_n: int,
    max_candidates: int,
) -> None:
    if keywords or section_priors:
        rule_candidates = _expand_rule_based(
            spans, keywords=keywords, section_priors=section_priors, top_n=per_step_top_n
        )
        for span, score in rule_candidates:
            _add_candidate(pool, span, score, "expand:rules")

    if queries:
        bm25_candidates = _expand_bm25(
            spans, bm25_index, queries=queries, top_n=per_step_top_n
        )
        for span, score in bm25_candidates:
            _add_candidate(pool, span, score, "expand:bm25")

    _trim_pool(pool, max_candidates)


def _expand_rule_based(
    spans: Sequence[SectionSpan],
    *,
    keywords: Sequence[str],
    section_priors: Sequence[str],
    top_n: int,
) -> List[Tuple[SectionSpan, float]]:
    ranked: List[Tuple[int, SectionSpan, float]] = []
    for idx, span in enumerate(spans):
        section_score, _matched_priors = score_section_title(span.title, section_priors)
        matched_keywords = _match_keywords(span.text, keywords)
        keyword_score = float(len(matched_keywords))
        if section_score == 0 and keyword_score == 0:
            continue
        score = float(section_score) * 10.0 + keyword_score
        ranked.append((idx, span, score))
    ranked.sort(
        key=lambda item: (
            -item[2],
            item[1].page if item[1].page is not None else 10_000,
            item[0],
        )
    )
    return [(span, score) for _, span, score in ranked[:top_n]]


def _expand_bm25(
    spans: Sequence[SectionSpan],
    index: BM25Index,
    *,
    queries: Sequence[str],
    top_n: int,
) -> List[Tuple[SectionSpan, float]]:
    best_by_pid: Dict[str, Tuple[SectionSpan, float]] = {}
    for query in queries:
        hits = index.search(query, top_n=top_n)
        for hit in hits:
            span = spans[hit.doc_index]
            existing = best_by_pid.get(span.paragraph_id)
            if existing is None or hit.score > existing[1]:
                best_by_pid[span.paragraph_id] = (span, float(hit.score))
    ranked = sorted(best_by_pid.values(), key=lambda item: (-item[1], item[0].paragraph_id))
    return ranked[:top_n]


def _match_keywords(text: str, keywords: Sequence[str]) -> List[str]:
    if not keywords:
        return []
    haystack = normalize_for_match(text)
    if not haystack:
        return []

    matched: List[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        needle = normalize_for_match(keyword)
        if not needle:
            continue
        hit = False
        if _is_short_token(needle):
            if re.search(rf"\\b{re.escape(needle)}\\b", haystack):
                hit = True
        else:
            if needle in haystack:
                hit = True
        if hit:
            key = keyword.casefold()
            if key not in seen:
                seen.add(key)
                matched.append(keyword)
    return matched


def _is_short_token(token: str) -> bool:
    return token.isascii() and len(token) <= 4 and token.isalnum()


def _trim_pool(pool: Dict[str, _CandidateInfo], max_candidates: int) -> None:
    if len(pool) <= max_candidates:
        return
    ranked = sorted(
        pool.items(), key=lambda item: (-item[1].score, item[0])
    )
    keep = dict(ranked[:max_candidates])
    pool.clear()
    pool.update(keep)


__all__ = ["llm_locator_node", "LLMLocatorConfig"]
