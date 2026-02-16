from __future__ import annotations

from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parents[2] / "src" / "llm" / "prompts" / "domains"

ALL_PROMPTS = [
    "d1_system.md",
    "d1_system.en.md",
    "d1_system.zh.md",
    "d2_system.md",
    "d2_system.en.md",
    "d2_system.zh.md",
    "d3_system.md",
    "d3_system.en.md",
    "d3_system.zh.md",
    "d4_system.md",
    "d4_system.en.md",
    "d4_system.zh.md",
    "d5_system.md",
    "d5_system.en.md",
    "d5_system.zh.md",
    "rob2_domain_system.md",
    "rob2_domain_system.en.md",
    "rob2_domain_system.zh.md",
]


def _load(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def test_all_domain_prompts_include_core_contract_and_placeholder() -> None:
    required_tokens = [
        "domain_risk",
        "domain_rationale",
        "answers",
        "domain_questions",
        "question_id",
        "options",
        "conditions",
        "evidence",
        "confidence",
        "NI",
        "NA",
        "{{effect_note}}",
    ]
    for name in ALL_PROMPTS:
        text = _load(name)
        for token in required_tokens:
            assert token in text, f"{name} missing token: {token}"

        if name.endswith(".zh.md"):
            assert "回退字段" in text, f"{name} missing fallback semantics"
            assert "逐字" in text, f"{name} missing verbatim quote constraint"
            assert "缺失" in text, f"{name} missing NI missing-info guidance"
            assert "未被当前逻辑路径触及" in text, f"{name} missing path reachability guidance"
            assert "必须返回 `domain_questions` 中全部 `question_id`" in text, (
                f"{name} missing all-question-id contract"
            )
            assert "必须回答 `NA`，且不得省略该问题" in text, (
                f"{name} missing unreached-NA no-omit contract"
            )
            assert "不输出该问题" not in text, (
                f"{name} still contains legacy omit guidance"
            )
        else:
            lowered = text.lower()
            assert "fallback fields" in lowered, f"{name} missing fallback semantics"
            assert "verbatim" in lowered, f"{name} missing verbatim quote constraint"
            assert "missing" in lowered, f"{name} missing NI missing-info guidance"
            assert (
                "not reached by the active logical path" in lowered
            ), f"{name} missing path reachability guidance"
            assert (
                "you must return all `question_id`s in `domain_questions`." in lowered
            ), f"{name} missing all-question-id contract"
            assert (
                "answer `na` and do not omit the question" in lowered
            ), f"{name} missing unreached-NA no-omit contract"
            assert "omit it, or answer na when required by the json structure" not in lowered, (
                f"{name} still contains legacy omit guidance"
            )
            assert "baseline guidance may say to omit it" not in lowered, (
                f"{name} still contains legacy baseline-omit guidance"
            )


def test_d2_prompts_cover_assignment_and_adherence_calibration() -> None:
    for name in ["d2_system.md", "d2_system.en.md", "d2_system.zh.md"]:
        text = _load(name).lower()
        assert "assignment" in text, f"{name} missing assignment calibration"
        assert "adherence" in text, f"{name} missing adherence calibration"


def test_d2_zh_prompt_uses_payload_question_ids_and_path_constraints() -> None:
    text = _load("d2_system.zh.md")
    assert "不得使用 `q2_1..q2_7` 作为返回键或作答题号" in text
    assert "`q2a_1` 答案为" in text
    assert "`q2a_7` 答案为" in text
    assert "`q2b_6` 应回答 NI" in text
    assert "`q2a_6` 优先级规则" in text
    assert "`q2b_4` 与 `q2b_5` 在出现在 payload 时属于激活题，不得回答 `NA`" in text
    assert "对缺失结局的处理不当可能影响结果" not in text


def test_d2_en_prompt_uses_payload_question_ids_and_path_constraints() -> None:
    text = _load("d2_system.en.md")
    lowered = text.lower()
    assert "do not use `q2_1..q2_7` as returned keys or answer question ids" in lowered
    assert "`q2a_1` answer must be y" in lowered
    assert "`q2a_7` answer must be n" in lowered
    assert "`q2a_6` priority rule" in lowered
    assert "`q2b_4` and `q2b_5` are active-path questions whenever they appear in payload; `na` is not allowed" in lowered
    assert "inappropriate handling of missing outcomes could affect results" not in lowered


def test_d4_prompts_include_tool_and_assessor_calibration() -> None:
    for name in ["d4_system.md", "d4_system.en.md"]:
        text = _load(name).lower()
        assert "mmse" in text, f"{name} missing standard-tool example"
        assert "assessor" in text, f"{name} missing assessor emphasis"

    zh_text = _load("d4_system.zh.md")
    assert "MMSE" in zh_text
    assert "评估者" in zh_text


def test_d4_en_prompt_orders_q4_4_ni_before_py() -> None:
    text = _load("d4_system.en.md").lower()
    assert "q4_4 decision order" in text
    assert "if missing, q4_4 answer must be ni" in text
    assert "only when measurement/ascertainment method is reported" in text


def test_fallback_prompt_templates_keep_strong_constraints() -> None:
    for name in [
        "rob2_domain_system.md",
        "rob2_domain_system.en.md",
        "rob2_domain_system.zh.md",
    ]:
        text = _load(name)
        assert "domain_questions" in text
        assert "question_id" in text
        assert "evidence" in text
        assert "{{effect_note}}" in text
