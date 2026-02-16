from __future__ import annotations

from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parents[2] / "src" / "llm" / "prompts" / "domains"


def _load(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def test_domain_prompt_templates_include_answer_constraint() -> None:
    names = [
        "d1_system.md",
        "d2_system.md",
        "d3_system.md",
        "d4_system.md",
        "d5_system.md",
        "rob2_domain_system.md",
    ]
    for name in names:
        text = _load(name)
        assert "options" in text
        assert "answer" in text
        assert "NA" in text
        assert "NI" in text


def test_domain_prompt_templates_include_condition_semantics() -> None:
    names = [
        "d1_system.md",
        "d2_system.md",
        "d3_system.md",
        "d4_system.md",
        "d5_system.md",
        "rob2_domain_system.md",
    ]
    for name in names:
        text = _load(name)
        assert "conditions" in text
        assert "operator" in text
        assert "dependencies" in text
        assert "question_id" in text
        assert "allowed_answers" in text
        assert "You must return all `question_id`s in `domain_questions`." in text
        assert "answer `NA` and do not omit the question" in text


def test_d2_zh_prompt_treats_questions_without_conditions_as_active() -> None:
    text = _load("d2_system.zh.md")
    assert "`domain_questions` 中无 `conditions` 的问题视为已激活题，不得回答 `NA`" in text
