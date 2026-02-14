"""Shared LLM reasoning helpers for ROB2 domain agents."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, TYPE_CHECKING, cast, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from core.config import get_settings
from rob2.decision_rules import evaluate_domain_risk_with_trace
from schemas.internal.decisions import (
    AnswerOption,
    DomainAnswer,
    DomainDecision,
    DomainRisk,
    EvidenceRef,
)
from schemas.internal.evidence import FusedEvidenceCandidate
from schemas.internal.locator import DomainId
from schemas.internal.rob2 import QuestionCondition, QuestionSet, Rob2Question
from utils.llm_json import extract_json_object

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


EffectType = Literal["assignment", "adherence"]


class ChatModelLike(Protocol):
    def with_structured_output(self, schema: type[BaseModel]) -> Any: ...
    def invoke(self, input: object) -> Any: ...


class _AnswerEvidence(BaseModel):
    paragraph_id: str
    quote: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class _AnswerOutput(BaseModel):
    question_id: str
    answer: AnswerOption
    rationale: str
    evidence: List[_AnswerEvidence] = Field(default_factory=list)
    confidence: Optional[float] = Field(default=None, ge=0, le=1)

    model_config = ConfigDict(extra="ignore")

    @field_validator("answer", mode="before")
    @classmethod
    def _normalize_answer_token(cls, value: object) -> object:
        if value is None:
            return value
        return str(value).strip().upper()


class _DecisionOutput(BaseModel):
    domain_risk: Optional[str] = None
    domain_rationale: Optional[str] = None
    answers: List[_AnswerOutput]

    model_config = ConfigDict(extra="ignore")


@dataclass(frozen=True)
class LLMReasoningConfig:
    model: str
    model_provider: str | None = None
    temperature: float = 0.0
    timeout: float | None = None
    max_tokens: int | None = None
    max_retries: int | None = 2


_RISK_MAP = {
    "low": "low",
    "some concerns": "some_concerns",
    "some_concerns": "some_concerns",
    "some-concerns": "some_concerns",
    "high": "high",
}
_PROMPTS_DIR = Path(__file__).resolve().parents[4] / "llm" / "prompts" / "domains"
_SYSTEM_PROMPT_FALLBACK = "rob2_domain_system.md"
_EFFECT_NOTE_PATTERN = re.compile(r"{{\s*effect_note\s*}}")
_RULE_TRACE_QUESTION_PATTERN = re.compile(r"q\d+[ab]?_\d+")


@lru_cache(maxsize=1)
def _read_prompt_lang() -> str:
    lang = str(get_settings().prompt_lang or "").strip().lower()
    return lang or "zh"


@lru_cache(maxsize=8)
def _load_system_prompt_template(domain: DomainId) -> str:
    domain_key = str(domain).lower()
    lang = _read_prompt_lang()
    candidates: List[Path] = []
    if lang:
        candidates.append(_PROMPTS_DIR / f"{domain_key}_system.{lang}.md")
    candidates.append(_PROMPTS_DIR / f"{domain_key}_system.md")
    if lang:
        candidates.append(_PROMPTS_DIR / f"rob2_domain_system.{lang}.md")
    candidates.append(_PROMPTS_DIR / _SYSTEM_PROMPT_FALLBACK)

    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "System prompt template not found. Tried: "
        + ", ".join(str(path) for path in candidates)
    )


def run_domain_reasoning(
    *,
    domain: DomainId,
    question_set: QuestionSet,
    validated_candidates: Mapping[str, Sequence[dict]],
    llm: ChatModelLike | None = None,
    llm_config: LLMReasoningConfig | None = None,
    effect_type: Optional[EffectType] = None,
    evidence_top_k: int = 5,
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None,
) -> DomainDecision:
    questions = _select_questions(question_set, domain, effect_type=effect_type)
    if not questions:
        raise ValueError(f"No questions found for domain {domain}.")

    evidence_by_q = _build_evidence_by_question(validated_candidates, questions, top_k=evidence_top_k)
    system_prompt = system_prompt or _build_system_prompt(domain, effect_type=effect_type)
    user_prompt = user_prompt or _build_user_prompt(questions, evidence_by_q, effect_type=effect_type)

    model = llm
    if model is None:
        if llm_config is None:
            raise ValueError("LLM config is required when llm is not provided.")
        model = _init_chat_model(llm_config)

    messages = _build_messages(system_prompt, user_prompt)
    response = _invoke_model(model, messages)
    decision = _normalize_decision(domain, questions, evidence_by_q, response, effect_type=effect_type)
    return decision


def build_domain_prompts(
    *,
    domain: DomainId,
    question_set: QuestionSet,
    validated_candidates: Mapping[str, Sequence[dict]],
    effect_type: Optional[EffectType] = None,
    evidence_top_k: int = 5,
) -> tuple[str, str]:
    questions = _select_questions(question_set, domain, effect_type=effect_type)
    if not questions:
        raise ValueError(f"No questions found for domain {domain}.")
    evidence_by_q = _build_evidence_by_question(validated_candidates, questions, top_k=evidence_top_k)
    system_prompt = _build_system_prompt(domain, effect_type=effect_type)
    user_prompt = _build_user_prompt(questions, evidence_by_q, effect_type=effect_type)
    return system_prompt, user_prompt


def _select_questions(
    question_set: QuestionSet,
    domain: DomainId,
    *,
    effect_type: Optional[EffectType] = None,
) -> List[Rob2Question]:
    selected = [
        question
        for question in question_set.questions
        if question.domain == domain
        and (effect_type is None or question.effect_type == effect_type)
    ]
    return sorted(selected, key=lambda item: item.order)


def _build_evidence_by_question(
    validated_candidates: Mapping[str, Sequence[dict]],
    questions: Sequence[Rob2Question],
    *,
    top_k: int,
) -> Dict[str, List[FusedEvidenceCandidate]]:
    evidence_by_q: Dict[str, List[FusedEvidenceCandidate]] = {}
    for question in questions:
        raw_list = validated_candidates.get(question.question_id) or []
        parsed = [FusedEvidenceCandidate.model_validate(item) for item in raw_list]
        evidence_by_q[question.question_id] = parsed[:top_k]
    return evidence_by_q


def _build_system_prompt(domain: DomainId, *, effect_type: Optional[EffectType]) -> str:
    effect_note = f"Effect type: {effect_type}." if effect_type else ""
    template = _load_system_prompt_template(domain)
    if _EFFECT_NOTE_PATTERN.search(template):
        prompt = _EFFECT_NOTE_PATTERN.sub(effect_note, template)
        return prompt.strip()
    if not effect_note:
        return template.strip()
    return f"{template.rstrip()}\n{effect_note}".strip()


def _build_user_prompt(
    questions: Sequence[Rob2Question],
    evidence_by_q: Mapping[str, Sequence[FusedEvidenceCandidate]],
    *,
    effect_type: Optional[EffectType],
) -> str:
    payload = {
        "domain_questions": [
            {
                "question_id": question.question_id,
                "text": question.text,
                "options": question.options,
                "conditions": _format_conditions(question.conditions),
            }
            for question in questions
        ],
        "evidence": {
            question.question_id: [
                {
                    "paragraph_id": candidate.paragraph_id,
                    "title": candidate.title,
                    "page": candidate.page,
                    "text": candidate.text,
                }
                for candidate in evidence_by_q.get(question.question_id) or []
            ]
            for question in questions
        },
        "effect_type": effect_type,
    }
    return json.dumps(payload, ensure_ascii=False)


def _format_conditions(conditions: Sequence[QuestionCondition]) -> List[dict]:
    formatted: List[dict] = []
    for condition in conditions:
        formatted.append(
            {
                "operator": condition.operator,
                "dependencies": [
                    {
                        "question_id": dependency.question_id,
                        "allowed_answers": dependency.allowed_answers,
                    }
                    for dependency in condition.dependencies
                ],
                "note": condition.note,
            }
        )
    return formatted


def _init_chat_model(config: LLMReasoningConfig) -> ChatModelLike:
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


def _build_messages(system_prompt: str, user_prompt: str) -> "list[BaseMessage]":
    from langchain_core.messages import HumanMessage, SystemMessage

    return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]


def _invoke_model(model: ChatModelLike, messages: list[BaseMessage]) -> _DecisionOutput:
    try:
        structured = model.with_structured_output(_DecisionOutput)
        result = structured.invoke(messages)
        if isinstance(result, _DecisionOutput):
            return result
    except Exception:
        pass

    raw = model.invoke(messages)
    content = getattr(raw, "content", raw)
    if not isinstance(content, str):
        content = str(content)
    return _parse_response(content)


def _parse_response(text: str) -> _DecisionOutput:
    extracted = _extract_json_object(text)
    try:
        payload = json.loads(extracted)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM domain reasoning did not return valid JSON") from exc
    try:
        return _DecisionOutput.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("LLM domain reasoning JSON did not match schema") from exc


def _extract_json_object(text: str) -> str:
    try:
        return extract_json_object(text, prefer_code_block=True)
    except ValueError as exc:
        raise ValueError("No JSON object found in LLM response") from exc


def _normalize_decision(
    domain: DomainId,
    questions: Sequence[Rob2Question],
    evidence_by_q: Mapping[str, Sequence[FusedEvidenceCandidate]],
    response: _DecisionOutput,
    *,
    effect_type: Optional[EffectType],
) -> DomainDecision:
    answer_map = _validate_and_index_answers(
        domain=domain,
        questions=questions,
        raw_answers=response.answers or [],
    )
    answers: List[DomainAnswer] = []
    missing_questions: List[str] = []

    normalized_answers: Dict[str, AnswerOption] = {
        question.question_id: answer_map[question.question_id].answer for question in questions
    }

    for question in questions:
        raw = answer_map[question.question_id]
        answer = normalized_answers.get(question.question_id, "NI")
        if not _conditions_met(question.conditions, normalized_answers):
            if "NA" in question.options:
                answer = "NA"
            else:
                answer = "NI"
        normalized_answers[question.question_id] = answer

        rationale = str(raw.rationale).strip() if raw and raw.rationale else ""
        confidence = raw.confidence if raw and raw.confidence is not None else None

        evidence_refs = _collect_evidence_refs(
            raw.evidence if raw else [], evidence_by_q.get(question.question_id) or []
        )
        if answer == "NI":
            missing_questions.append(question.question_id)

        answers.append(
            DomainAnswer(
                question_id=question.question_id,
                answer=cast(Any, answer),
                rationale=rationale or "Insufficient evidence to answer confidently.",
                evidence_refs=evidence_refs,
                confidence=confidence,
            )
        )

    rule_risk, rule_trace = evaluate_domain_risk_with_trace(
        domain,
        normalized_answers,
        effect_type=effect_type,
    )
    if rule_risk is not None:
        risk: DomainRisk = rule_risk
        risk_rationale = _build_rule_based_rationale(
            domain=domain,
            effect_type=effect_type,
            rule_trace=rule_trace,
            normalized_answers=normalized_answers,
        )
        final_rule_trace = list(rule_trace)
    else:
        llm_risk = _normalize_llm_risk(response.domain_risk)
        if llm_risk is None:
            raise ValueError(
                "LLM fallback domain_risk is missing or invalid "
                f"(domain={domain}, effect_type={effect_type}, rule_trace={rule_trace})"
            )
        risk = llm_risk
        risk_rationale = (
            str(response.domain_rationale or "").strip()
            or "No domain-level rationale provided."
        )
        final_rule_trace = [
            *rule_trace,
            "FALLBACK: rule_unavailable -> llm_domain_risk",
        ]

    return DomainDecision(
        domain=domain,
        effect_type=effect_type,
        risk=risk,
        risk_rationale=risk_rationale,
        answers=answers,
        missing_questions=missing_questions,
        rule_trace=final_rule_trace,
    )


def _validate_and_index_answers(
    *,
    domain: DomainId,
    questions: Sequence[Rob2Question],
    raw_answers: Sequence[_AnswerOutput],
) -> Dict[str, _AnswerOutput]:
    question_by_id = {question.question_id: question for question in questions}
    indexed: Dict[str, _AnswerOutput] = {}

    for item in raw_answers:
        question = question_by_id.get(item.question_id)
        if question is None:
            raise ValueError(
                _answer_validation_error(
                    domain=domain,
                    error_type="unknown",
                    question_id=item.question_id,
                    answer=item.answer,
                    allowed_options=[],
                )
            )
        if item.question_id in indexed:
            raise ValueError(
                _answer_validation_error(
                    domain=domain,
                    error_type="duplicate",
                    question_id=item.question_id,
                    answer=item.answer,
                    allowed_options=question.options,
                )
            )
        if item.answer not in question.options:
            raise ValueError(
                _answer_validation_error(
                    domain=domain,
                    error_type="invalid",
                    question_id=item.question_id,
                    answer=item.answer,
                    allowed_options=question.options,
                )
            )
        indexed[item.question_id] = item

    for question in questions:
        if question.question_id in indexed:
            continue
        raise ValueError(
            _answer_validation_error(
                domain=domain,
                error_type="missing",
                question_id=question.question_id,
                answer="<missing>",
                allowed_options=question.options,
            )
        )

    return indexed


def _answer_validation_error(
    *,
    domain: DomainId,
    error_type: str,
    question_id: str,
    answer: object,
    allowed_options: Sequence[str],
) -> str:
    return (
        "LLM answers validation failed "
        f"(domain={domain}, error_type={error_type}, question_id={question_id}, "
        f"answer={answer}, allowed_options={list(allowed_options)})"
    )


def _build_rule_based_rationale(
    *,
    domain: DomainId,
    effect_type: Optional[EffectType],
    rule_trace: Sequence[str],
    normalized_answers: Mapping[str, AnswerOption],
) -> str:
    trace_line = rule_trace[0] if rule_trace else f"{domain}:R0 no rule trace"
    question_ids = _extract_rule_question_ids(rule_trace)
    if not question_ids:
        question_ids = list(normalized_answers.keys())
    key_answers = ", ".join(
        f"{question_id}={normalized_answers.get(question_id, 'NI')}"
        for question_id in question_ids[:6]
    )
    effect_suffix = f"/{effect_type}" if effect_type else ""
    if key_answers:
        return (
            f"Rule tree determined risk for {domain}{effect_suffix}. "
            f"Matched rule: {trace_line}. Key answers: {key_answers}."
        )
    return f"Rule tree determined risk for {domain}{effect_suffix}. Matched rule: {trace_line}."


def _extract_rule_question_ids(rule_trace: Sequence[str]) -> List[str]:
    question_ids: List[str] = []
    seen: set[str] = set()
    for line in rule_trace:
        for question_id in _RULE_TRACE_QUESTION_PATTERN.findall(line):
            if question_id in seen:
                continue
            seen.add(question_id)
            question_ids.append(question_id)
    return question_ids


def _normalize_llm_risk(value: Optional[str]) -> DomainRisk | None:
    key = str(value or "").strip().lower()
    normalized = _RISK_MAP.get(key)
    if normalized is None:
        return None
    return cast(DomainRisk, normalized)


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


def _collect_evidence_refs(
    evidence: Sequence[_AnswerEvidence],
    candidates: Sequence[FusedEvidenceCandidate],
) -> List[EvidenceRef]:
    candidates_by_pid = {candidate.paragraph_id: candidate for candidate in candidates}
    refs: List[EvidenceRef] = []
    for item in evidence:
        candidate = candidates_by_pid.get(item.paragraph_id)
        if candidate is None:
            continue
        refs.append(
            EvidenceRef(
                paragraph_id=candidate.paragraph_id,
                page=candidate.page,
                title=candidate.title,
                quote=item.quote,
            )
        )
    return refs


def build_reasoning_config(
    *,
    model_id: str,
    model_provider: Optional[str],
    temperature: float,
    timeout: Optional[float],
    max_tokens: Optional[int],
    max_retries: int,
) -> LLMReasoningConfig:
    return LLMReasoningConfig(
        model=model_id,
        model_provider=model_provider,
        temperature=temperature,
        timeout=timeout,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )


def read_domain_llm_config(
    state: Mapping[str, Any],
    *,
    prefix: str,
    default_temperature: float = 0.0,
    default_max_retries: int = 2,
) -> tuple[LLMReasoningConfig, dict[str, Any]]:
    model_id = _read_str(state.get(f"{prefix}_model"))
    model_provider = _read_str(state.get(f"{prefix}_model_provider"))
    temperature = _read_float(state.get(f"{prefix}_temperature"), default_temperature)
    timeout = _read_optional_float(state.get(f"{prefix}_timeout"))
    max_tokens = _read_optional_int(state.get(f"{prefix}_max_tokens"))
    max_retries = _read_int(state.get(f"{prefix}_max_retries"), default_max_retries)

    config = LLMReasoningConfig(
        model=model_id or "",
        model_provider=model_provider,
        temperature=temperature,
        timeout=timeout,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )
    return config, {
        "model": model_id or "",
        "model_provider": model_provider,
        "temperature": temperature,
        "timeout": timeout,
        "max_tokens": max_tokens,
        "max_retries": max_retries,
    }


def _read_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _read_int(value: Any, default: int) -> int:
    if value is None:
        return int(default)
    return int(str(value))


def _read_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(str(value))


def _read_float(value: Any, default: float) -> float:
    if value is None:
        return float(default)
    return float(str(value))


def _read_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(str(value))


__all__ = [
    "ChatModelLike",
    "EffectType",
    "LLMReasoningConfig",
    "build_domain_prompts",
    "build_reasoning_config",
    "read_domain_llm_config",
    "run_domain_reasoning",
]
