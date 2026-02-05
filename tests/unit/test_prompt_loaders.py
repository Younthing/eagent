from __future__ import annotations

from pathlib import Path

from evidence.validators import relevance as relevance_mod
from evidence.validators import consistency as consistency_mod
from retrieval.query_planning import llm as planner_mod


def test_relevance_prompt_loaded_from_file() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "llm"
        / "prompts"
        / "validators"
        / "relevance_system.md"
    )
    expected = path.read_text(encoding="utf-8").strip()
    assert relevance_mod._load_relevance_system_prompt().strip() == expected


def test_consistency_prompt_loaded_from_file() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "llm"
        / "prompts"
        / "validators"
        / "consistency_system.md"
    )
    expected = path.read_text(encoding="utf-8").strip()
    assert consistency_mod._load_consistency_system_prompt().strip() == expected


def test_query_planner_prompt_loaded_from_file_and_substituted() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "llm"
        / "prompts"
        / "planners"
        / "query_planner_system.md"
    )
    raw = path.read_text(encoding="utf-8").strip()
    prompt = planner_mod._load_query_planner_system_prompt(max_queries=3)
    assert "{{max_queries}}" not in prompt
    assert str(3) in prompt
    assert raw.strip().replace("{{max_queries}}", "3") in prompt
