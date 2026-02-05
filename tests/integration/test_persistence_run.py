from __future__ import annotations

from pathlib import Path
from typing import Any

from schemas.requests import Rob2Input
from services import rob2_runner


def test_run_rob2_persists_minimal(tmp_path: Path, monkeypatch) -> None:
    final_state = {
        "rob2_result": {
            "variant": "standard",
            "question_set_version": "1.0",
            "overall": {"risk": "low", "rationale": "ok"},
            "domains": [
                {
                    "domain": "D1",
                    "risk": "low",
                    "risk_rationale": "ok",
                    "answers": [
                        {
                            "question_id": "q1",
                            "answer": "Y",
                            "rationale": "ok",
                            "evidence_refs": [],
                        }
                    ],
                    "missing_questions": [],
                    "rule_trace": [],
                }
            ],
            "citations": [],
        },
        "rob2_table_markdown": "| Table |",
        "question_set": {"version": "1.0", "variant": "standard", "questions": []},
        "doc_structure": {"body": "", "sections": []},
        "validated_candidates": {},
        "relevance_config": {},
        "relevance_debug": {},
        "consistency_reports": {},
        "completeness_report": [],
        "validation_retry_log": [],
        "domain_audit_reports": [],
    }

    class DummyGraph:
        def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
            return final_state

    monkeypatch.setattr(rob2_runner, "build_rob2_graph", lambda: DummyGraph())

    result = rob2_runner.run_rob2(
        Rob2Input(pdf_bytes=b"%PDF-1.4", filename="test.pdf"),
        {},
        persist_enabled=True,
        persistence_dir=str(tmp_path),
        cache_scope="none",
    )

    assert result.run_id
    run_dir = tmp_path / "runs" / result.run_id
    assert (run_dir / "result.json").exists()
    assert (run_dir / "run_manifest.json").exists()
    assert (tmp_path / "metadata.sqlite").exists()
