"""Full-text domain audit + evidence patch nodes (Milestone 9).

Per-domain audit nodes:
- Read the full document (`doc_structure.sections`) and ONLY one domain's questions.
- Compare audit answers with the domain agent answers.
- Patch `validated_candidates` using audit citations, then immediately re-run that domain.

Optional final audit node:
- Runs once after D5 to audit all domains in a single call (switchable).
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.config import get_settings
from schemas.internal.decisions import AnswerOption, DomainDecision
from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.evidence import (
    EvidenceSupport,
    FusedEvidenceCandidate,
    RelevanceVerdict,
)
from schemas.internal.locator import DomainId
from schemas.internal.rob2 import QuestionCondition, QuestionSet, Rob2Question
from utils.text import normalize_block
from utils.llm_json import extract_json_object

from pipelines.graphs.nodes.domains.d1_randomization import d1_randomization_node
from pipelines.graphs.nodes.domains.d2_deviations import d2_deviations_node
from pipelines.graphs.nodes.domains.d3_missing_data import d3_missing_data_node
from pipelines.graphs.nodes.domains.d4_measurement import d4_measurement_node
from pipelines.graphs.nodes.domains.d5_reporting import d5_reporting_node


AuditMode = str  # "none" | "llm"

_WHITESPACE = re.compile(r"\s+")
_DEFAULT_AUDIT_MAX_RETRIES = 2
_DEFAULT_AUDIT_PATCH_WINDOW = 0
_DEFAULT_AUDIT_MAX_PATCHES = 3


class ChatModelLike:
    def with_structured_output(self, schema: type[BaseModel]) -> Any: ...

    def invoke(self, input: object) -> Any: ...


class _AuditEvidence(BaseModel):
    paragraph_id: Optional[str] = None
    quote: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class _AuditAnswer(BaseModel):
    question_id: str
    answer: str
    rationale: str = ""
    evidence: List[_AuditEvidence] = Field(default_factory=list)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)

    model_config = ConfigDict(extra="ignore")


class _AuditOutput(BaseModel):
    answers: List[_AuditAnswer]

    model_config = ConfigDict(extra="ignore")


@lru_cache(maxsize=1)
def _read_prompt_lang() -> str:
    lang = str(get_settings().prompt_lang or "").strip().lower()
    return lang or "zh"


@lru_cache(maxsize=1)
def _load_audit_system_prompt() -> str:
    prompt_dir = Path(__file__).resolve().parents[3] / "llm" / "prompts" / "validators"
    lang = _read_prompt_lang()
    candidates: List[Path] = []
    if lang:
        candidates.append(prompt_dir / f"domain_audit_system.{lang}.md")
    candidates.append(prompt_dir / "domain_audit_system.md")

    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    return (
        "You are a strict ROB2 audit assistant.\n"
        "Given ROB2 signaling questions and a full document represented as a list of\n"
        "paragraph spans with paragraph_id, answer each question using only the document.\n"
        "Always cite evidence with paragraph_id and an exact quote from that paragraph.\n"
        "Return JSON matching the requested schema."
    )


def d1_audit_node(state: dict) -> dict:
    return _run_domain_audit_node(state, domain="D1")


def d2_audit_node(state: dict) -> dict:
    effect_type = str(state.get("d2_effect_type") or "assignment").strip().lower()
    return _run_domain_audit_node(state, domain="D2", effect_type=effect_type)


def d3_audit_node(state: dict) -> dict:
    return _run_domain_audit_node(state, domain="D3")


def d4_audit_node(state: dict) -> dict:
    return _run_domain_audit_node(state, domain="D4")


def d5_audit_node(state: dict) -> dict:
    return _run_domain_audit_node(state, domain="D5")


def final_domain_audit_node(state: dict) -> dict:
    effect_type = str(state.get("d2_effect_type") or "assignment").strip().lower()
    return _run_all_domains_audit_node(state, effect_type=effect_type)


def _run_domain_audit_node(
    state: dict,
    *,
    domain: DomainId,
    effect_type: Optional[str] = None,
) -> dict:
    raw_doc = state.get("doc_structure")
    if raw_doc is None:
        raise ValueError("domain_audit_node requires 'doc_structure'.")
    doc_structure = DocStructure.model_validate(raw_doc)

    raw_questions = state.get("question_set")
    if raw_questions is None:
        raise ValueError("domain_audit_node requires 'question_set'.")
    question_set = QuestionSet.model_validate(raw_questions)

    raw_candidates = state.get("validated_candidates")
    if raw_candidates is None:
        raise ValueError("domain_audit_node requires 'validated_candidates'.")
    if not isinstance(raw_candidates, Mapping):
        raise ValueError("validated_candidates must be a mapping")

    mode = _read_audit_mode(state)
    if mode == "none":
        report = {"domain": domain, "mode": "none", "enabled": False}
        return {
            "domain_audit_reports": [report],
            "domain_audit_report": report,
        }

    llm, model_kwargs = _read_audit_llm(state)
    patch_window, max_patches = _read_patch_config(state)
    rerun_enabled = _read_rerun_enabled(state)

    audit_questions = _select_domain_questions(
        question_set, domain=domain, effect_type=effect_type
    )
    messages = _build_messages(
        system_prompt=_load_audit_system_prompt(),
        user_prompt=_build_user_prompt(audit_questions, doc_structure),
    )
    audit_output = _invoke_audit_model(llm=llm, messages=messages, **model_kwargs)

    audit_answer_map, audit_evidence_map, audit_confidence_map = _normalize_audit_answers(
        audit_questions, audit_output
    )
    domain_answer_map = _domain_answer_map_from_state(state, domain=domain)

    mismatches = _compute_mismatches(
        audit_questions,
        audit_answer_map,
        domain_answer_map,
        audit_confidence_map,
        audit_evidence_map,
        domain=domain,
    )

    spans = list(doc_structure.sections)
    spans_by_pid = {span.paragraph_id: span for span in spans}
    index_by_pid = {span.paragraph_id: idx for idx, span in enumerate(spans)}

    updated_candidates: Dict[str, List[dict]] = {
        k: list(v) if isinstance(v, list) else [] for k, v in raw_candidates.items()
    }
    patches_applied: Dict[str, List[dict]] = {}

    for mismatch in mismatches:
        question_id = mismatch["question_id"]
        evidence = cast(List[dict], mismatch.get("audit_evidence") or [])
        patch = _build_patch_candidates(
            question_id,
            evidence,
            spans=spans,
            spans_by_pid=spans_by_pid,
            index_by_pid=index_by_pid,
            window=patch_window,
            limit=max_patches,
        )
        if not patch:
            continue
        merged = [*patch, *(updated_candidates.get(question_id) or [])]
        deduped: List[dict] = []
        seen: set[str] = set()
        for item in merged:
            if not isinstance(item, dict):
                continue
            pid = item.get("paragraph_id")
            if not isinstance(pid, str) or not pid.strip():
                continue
            if pid in seen:
                continue
            seen.add(pid)
            deduped.append(item)
        updated_candidates[question_id] = deduped
        patches_applied[question_id] = patch

    report: dict[str, Any] = {
        "domain": domain,
        "mode": "llm",
        "enabled": True,
        **_report_model_fields(model_kwargs),
        "audited_questions": len(audit_questions),
        "mismatches": mismatches,
        "patch_window": patch_window,
        "patches_applied": {qid: len(items) for qid, items in patches_applied.items()},
        "rerun_enabled": rerun_enabled,
    }

    updates: Dict[str, Any] = {
        "validated_candidates": updated_candidates,
        "domain_audit_reports": [report],
        "domain_audit_report": report,
    }

    if rerun_enabled and patches_applied:
        updates.update(_rerun_domain_agent(state, updated_candidates, domain))
        report["domain_rerun"] = True
    else:
        report["domain_rerun"] = False
    return updates


def _run_all_domains_audit_node(state: dict, *, effect_type: str) -> dict:
    """Optional final audit: one audit call across all domains."""
    raw_doc = state.get("doc_structure")
    if raw_doc is None:
        raise ValueError("domain_audit_node requires 'doc_structure'.")
    doc_structure = DocStructure.model_validate(raw_doc)

    raw_questions = state.get("question_set")
    if raw_questions is None:
        raise ValueError("domain_audit_node requires 'question_set'.")
    question_set = QuestionSet.model_validate(raw_questions)

    mode = _read_audit_mode(state)
    if mode == "none":
        report = {"domain": "ALL", "mode": "none", "enabled": False}
        return {"domain_audit_reports": [report], "domain_audit_report": report}

    llm, model_kwargs = _read_audit_llm(state)

    audit_questions = _select_all_questions(question_set, effect_type=effect_type)
    messages = _build_messages(
        system_prompt=_load_audit_system_prompt(),
        user_prompt=_build_user_prompt(audit_questions, doc_structure),
    )
    audit_output = _invoke_audit_model(llm=llm, messages=messages, **model_kwargs)

    audit_answer_map, audit_evidence_map, audit_confidence_map = _normalize_audit_answers(
        audit_questions, audit_output
    )
    domain_answer_map = _domain_answer_map_from_state(state, domain=None)
    mismatches = _compute_mismatches(
        audit_questions,
        audit_answer_map,
        domain_answer_map,
        audit_confidence_map,
        audit_evidence_map,
        domain=None,
    )

    report: dict[str, Any] = {
        "domain": "ALL",
        "mode": "llm",
        "enabled": True,
        **_report_model_fields(model_kwargs),
        "audited_questions": len(audit_questions),
        "mismatches": mismatches,
    }
    return {
        "domain_audit_reports": [report],
        "domain_audit_report": report,
    }


def _select_all_questions(question_set: QuestionSet, *, effect_type: str) -> List[Rob2Question]:
    normalized_effect = effect_type.strip().lower()
    questions: List[Rob2Question] = []
    for question in question_set.questions:
        if question.domain != "D2":
            questions.append(question)
            continue
        if (question.effect_type or "assignment").strip().lower() == normalized_effect:
            questions.append(question)
    return sorted(questions, key=lambda q: (q.domain, q.order))


def _select_domain_questions(
    question_set: QuestionSet,
    *,
    domain: DomainId,
    effect_type: Optional[str],
) -> List[Rob2Question]:
    questions: List[Rob2Question] = []
    normalized_effect = (effect_type or "assignment").strip().lower()
    for question in question_set.questions:
        if question.domain != domain:
            continue
        if domain == "D2":
            if (question.effect_type or "assignment").strip().lower() != normalized_effect:
                continue
        questions.append(question)
    return sorted(questions, key=lambda q: q.order)


def _read_audit_mode(state: Mapping[str, Any]) -> AuditMode:
    mode = str(state.get("domain_audit_mode") or "none").strip().lower()
    if mode in {"0", "false", "off"}:
        mode = "none"
    if mode not in {"none", "llm"}:
        raise ValueError("domain_audit_mode must be 'none' or 'llm'")
    return mode


def _read_audit_llm(state: Mapping[str, Any]) -> tuple[Optional[ChatModelLike], dict[str, Any]]:
    llm = cast(Optional[ChatModelLike], state.get("domain_audit_llm"))
    model_id = str(
        state.get("domain_audit_model")
        or state.get("d1_model")
        or ""
    ).strip()
    model_provider = state.get("domain_audit_model_provider")
    temperature = (
        0.0
        if state.get("domain_audit_temperature") is None
        else float(str(state.get("domain_audit_temperature")))
    )
    timeout = (
        None
        if state.get("domain_audit_timeout") is None
        else float(str(state.get("domain_audit_timeout")))
    )
    max_tokens = (
        None
        if state.get("domain_audit_max_tokens") is None
        else int(str(state.get("domain_audit_max_tokens")))
    )
    max_retries = (
        _DEFAULT_AUDIT_MAX_RETRIES
        if state.get("domain_audit_max_retries") is None
        else int(str(state.get("domain_audit_max_retries")))
    )

    if llm is None and not model_id:
        raise ValueError("Missing audit model (set DOMAIN_AUDIT_MODEL or provide state['domain_audit_llm']).")

    return llm, {
        "model_id": model_id,
        "model_provider": str(model_provider) if model_provider else None,
        "temperature": temperature,
        "timeout": timeout,
        "max_tokens": max_tokens,
        "max_retries": max_retries,
    }


def _report_model_fields(model_kwargs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "model": model_kwargs.get("model_id"),
        "model_provider": model_kwargs.get("model_provider"),
    }


def _read_patch_config(state: Mapping[str, Any]) -> tuple[int, int]:
    patch_window = int(state.get("domain_audit_patch_window") or _DEFAULT_AUDIT_PATCH_WINDOW)
    max_patches = int(
        state.get("domain_audit_max_patches_per_question")
        or _DEFAULT_AUDIT_MAX_PATCHES
    )
    return patch_window, max_patches


def _read_rerun_enabled(state: Mapping[str, Any]) -> bool:
    if state.get("domain_audit_rerun_domains") is None:
        return False
    return bool(state.get("domain_audit_rerun_domains"))


def _build_user_prompt(questions: Sequence[Rob2Question], doc_structure: DocStructure) -> str:
    payload = {
        "domain_questions": [
            {
                "question_id": q.question_id,
                "domain": q.domain,
                "effect_type": q.effect_type,
                "text": q.text,
                "options": q.options,
                "conditions": _format_conditions(q.conditions),
            }
            for q in questions
        ],
        "document_spans": [
            {
                "paragraph_id": span.paragraph_id,
                "title": span.title,
                "page": span.page,
                "text": span.text,
            }
            for span in doc_structure.sections
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def _format_conditions(conditions: Sequence[QuestionCondition]) -> List[dict]:
    formatted: List[dict] = []
    for condition in conditions:
        formatted.append(condition.model_dump())
    return formatted


def _build_messages(system_prompt: str, user_prompt: str) -> "list[Any]":
    from langchain_core.messages import HumanMessage, SystemMessage

    return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]


def _invoke_audit_model(
    *,
    llm: Optional[ChatModelLike],
    model_id: str,
    model_provider: Optional[str],
    temperature: float,
    timeout: Optional[float],
    max_tokens: Optional[int],
    max_retries: int,
    messages: list[Any],
) -> _AuditOutput:
    model = llm
    if model is None:
        from langchain.chat_models import init_chat_model

        kwargs: dict[str, Any] = {}
        if model_provider:
            kwargs["model_provider"] = model_provider
        kwargs["temperature"] = temperature
        if timeout is not None:
            kwargs["timeout"] = timeout
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        kwargs["max_retries"] = max_retries
        model = cast(ChatModelLike, init_chat_model(model_id, **kwargs))

    try:
        structured = model.with_structured_output(_AuditOutput)
        result = structured.invoke(messages)
        if isinstance(result, _AuditOutput):
            return result
    except Exception:
        pass

    raw = model.invoke(messages)
    content = getattr(raw, "content", raw)
    if not isinstance(content, str):
        content = str(content)
    return _parse_audit_response(content)


def _parse_audit_response(text: str) -> _AuditOutput:
    extracted = _extract_json_object(text)
    try:
        payload = json.loads(extracted)
    except json.JSONDecodeError as exc:
        raise ValueError("Audit model did not return valid JSON") from exc
    try:
        return _AuditOutput.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Audit model JSON did not match schema") from exc


def _extract_json_object(text: str) -> str:
    try:
        return extract_json_object(text, prefer_code_block=True)
    except ValueError as exc:
        raise ValueError("No JSON object found in audit response") from exc


def _normalize_audit_answers(
    questions: Sequence[Rob2Question],
    output: _AuditOutput,
) -> tuple[dict[str, AnswerOption], dict[str, List[dict]], dict[str, Optional[float]]]:
    answer_map = {item.question_id: item for item in output.answers or []}
    normalized: Dict[str, AnswerOption] = {}
    evidence_map: Dict[str, List[dict]] = {}
    confidence_map: Dict[str, Optional[float]] = {}

    for question in questions:
        raw = answer_map.get(question.question_id)
        raw_answer = str(raw.answer).strip().upper() if raw else "NI"
        normalized_answer = cast(AnswerOption, _normalize_answer(raw_answer, question.options))
        normalized[question.question_id] = normalized_answer

    for question in questions:
        answer = normalized.get(question.question_id, cast(AnswerOption, "NI"))
        if not _conditions_met(question.conditions, normalized):
            answer = cast(AnswerOption, "NA" if "NA" in question.options else "NI")
        normalized[question.question_id] = answer

        raw = answer_map.get(question.question_id)
        evidence_map[question.question_id] = [
            {"paragraph_id": item.paragraph_id, "quote": item.quote}
            for item in (raw.evidence if raw else [])
            if (item.paragraph_id or item.quote)
        ]
        confidence_map[question.question_id] = raw.confidence if raw else None

    return normalized, evidence_map, confidence_map


def _normalize_answer(value: str, options: Sequence[str]) -> str:
    candidate = value.strip().upper()
    if candidate in options:
        return candidate
    if candidate == "NA" and "NA" in options:
        return "NA"
    return "NI"


def _conditions_met(
    conditions: Sequence[QuestionCondition],
    answers: Mapping[str, str],
) -> bool:
    if not conditions:
        return True
    for condition in conditions:
        hits = [
            answers.get(dependency.question_id) in dependency.allowed_answers
            for dependency in condition.dependencies
        ]
        if condition.operator == "any":
            if any(hits):
                return True
        else:
            if all(hits):
                return True
    return False


def _domain_answer_map_from_state(
    state: Mapping[str, Any],
    *,
    domain: DomainId | None,
) -> dict[str, AnswerOption]:
    answer_map: Dict[str, AnswerOption] = {}
    for key in ("d1_decision", "d2_decision", "d3_decision", "d4_decision", "d5_decision"):
        raw = state.get(key)
        if raw is None:
            continue
        try:
            decision = DomainDecision.model_validate(raw)
        except Exception:
            continue
        if domain is not None and decision.domain != domain:
            continue
        for answer in decision.answers:
            answer_map[answer.question_id] = answer.answer
    return answer_map


def _compute_mismatches(
    questions: Sequence[Rob2Question],
    audit_answers: Mapping[str, AnswerOption],
    domain_answers: Mapping[str, AnswerOption],
    confidence_map: Mapping[str, Optional[float]],
    evidence_map: Mapping[str, List[dict]],
    *,
    domain: DomainId | None,
) -> List[dict]:
    mismatches: List[dict] = []
    for q in questions:
        qid = q.question_id
        domain_answer = domain_answers.get(qid)
        if domain_answer is None:
            continue
        audit_answer = audit_answers.get(qid, cast(AnswerOption, "NI"))
        if audit_answer == domain_answer:
            continue
        mismatches.append(
            {
                "question_id": qid,
                "domain": domain or q.domain,
                "effect_type": q.effect_type,
                "domain_answer": domain_answer,
                "audit_answer": audit_answer,
                "audit_confidence": confidence_map.get(qid),
                "audit_evidence": evidence_map.get(qid) or [],
            }
        )
    return mismatches


def _build_patch_candidates(
    question_id: str,
    evidence: Sequence[Mapping[str, Any]],
    *,
    spans: Sequence[SectionSpan],
    spans_by_pid: Mapping[str, SectionSpan],
    index_by_pid: Mapping[str, int],
    window: int,
    limit: int,
) -> List[dict]:
    resolved: List[Tuple[str, Optional[str]]] = []
    for item in evidence:
        pid_raw = item.get("paragraph_id")
        quote_raw = item.get("quote")
        pid = str(pid_raw).strip() if isinstance(pid_raw, str) and pid_raw.strip() else None
        quote = str(quote_raw).strip() if isinstance(quote_raw, str) and quote_raw.strip() else None
        if pid and pid in spans_by_pid:
            resolved.append((pid, quote))
            continue
        if quote:
            found = _find_paragraph_id_by_quote(quote, spans)
            if found:
                resolved.append((found, quote))

    patch_candidates: List[FusedEvidenceCandidate] = []
    seen: set[str] = set()
    for pid, quote in resolved:
        for neighbor_pid, neighbor_quote in _expand_window(pid, quote, index_by_pid=index_by_pid, spans=spans, window=window):
            if neighbor_pid in seen:
                continue
            seen.add(neighbor_pid)
            span = spans_by_pid.get(neighbor_pid)
            if span is None:
                continue
            patch_candidates.append(
                _candidate_from_span(
                    question_id,
                    span,
                    supporting_quote=neighbor_quote,
                    fusion_rank=len(patch_candidates) + 1,
                )
            )
            if len(patch_candidates) >= limit:
                break
        if len(patch_candidates) >= limit:
            break

    # Deterministic grounding: paragraph_id must exist; quote (when present) must match.
    verified: List[dict] = []
    for candidate in patch_candidates:
        if candidate.paragraph_id not in spans_by_pid:
            continue
        if candidate.relevance and candidate.relevance.supporting_quote:
            quote = candidate.relevance.supporting_quote
            span = spans_by_pid[candidate.paragraph_id]
            if not _quote_in_text(quote, span.text):
                continue
        verified.append(candidate.model_dump())

    return verified


def _candidate_from_span(
    question_id: str,
    span: SectionSpan,
    *,
    supporting_quote: Optional[str],
    fusion_rank: int,
) -> FusedEvidenceCandidate:
    return FusedEvidenceCandidate(
        question_id=question_id,
        paragraph_id=span.paragraph_id,
        title=span.title,
        page=span.page,
        text=span.text,
        fusion_score=1.0,
        fusion_rank=max(1, int(fusion_rank)),
        support_count=1,
        supports=[EvidenceSupport(engine="audit", rank=1, score=1.0)],
        relevance=RelevanceVerdict(
            label="relevant",
            confidence=1.0,
            supporting_quote=supporting_quote,
        )
        if supporting_quote
        else None,
    )


def _expand_window(
    paragraph_id: str,
    quote: Optional[str],
    *,
    index_by_pid: Mapping[str, int],
    spans: Sequence[SectionSpan],
    window: int,
) -> Iterable[Tuple[str, Optional[str]]]:
    idx = index_by_pid.get(paragraph_id)
    if idx is None:
        yield paragraph_id, quote
        return
    start = max(0, idx - max(0, window))
    end = min(len(spans) - 1, idx + max(0, window))
    for i in range(start, end + 1):
        pid = spans[i].paragraph_id
        yield pid, quote if pid == paragraph_id else None


def _find_paragraph_id_by_quote(quote: str, spans: Sequence[SectionSpan]) -> Optional[str]:
    target = normalize_block(quote)
    if target:
        for span in spans:
            if target in (span.text or ""):
                return span.paragraph_id

    folded = _fold_whitespace(quote)
    if folded:
        for span in spans:
            if folded and folded in _fold_whitespace(span.text or ""):
                return span.paragraph_id

    lowered = folded.lower() if folded else ""
    if lowered:
        for span in spans:
            if lowered in _fold_whitespace(span.text or "").lower():
                return span.paragraph_id

    return None


def _fold_whitespace(text: str) -> str:
    return _WHITESPACE.sub(" ", text or "").strip()


def _quote_in_text(quote: str, text: str) -> bool:
    folded_quote = _fold_whitespace(quote)
    folded_text = _fold_whitespace(text)
    if not folded_quote:
        return True
    if folded_quote in folded_text:
        return True
    return folded_quote.lower() in folded_text.lower()


def _rerun_domain_agent(
    state: Mapping[str, Any],
    validated_candidates: Mapping[str, Sequence[dict]],
    domain: DomainId,
) -> dict:
    base_state: dict = dict(state)
    base_state["validated_candidates"] = dict(validated_candidates)
    if domain == "D1":
        return d1_randomization_node(base_state)
    if domain == "D2":
        return d2_deviations_node(base_state)
    if domain == "D3":
        return d3_missing_data_node(base_state)
    if domain == "D4":
        return d4_measurement_node(base_state)
    return d5_reporting_node(base_state)


__all__ = [
    "d1_audit_node",
    "d2_audit_node",
    "d3_audit_node",
    "d4_audit_node",
    "d5_audit_node",
    "final_domain_audit_node",
]
