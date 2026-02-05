from __future__ import annotations

from pathlib import Path

from reporting.batch_plot import (
    build_traffic_light_rows,
    generate_batch_traffic_light_png,
    normalize_risk,
)


def test_normalize_risk_supports_legacy_some_concerns_values() -> None:
    assert normalize_risk("some concerns") == "some_concerns"
    assert normalize_risk("some-concerns") == "some_concerns"
    assert normalize_risk("some_concerns") == "some_concerns"
    assert normalize_risk("low") == "low"
    assert normalize_risk("high") == "high"
    assert normalize_risk(None) == "not_applicable"


def test_build_rows_defaults_to_success_and_skipped_with_risk() -> None:
    summary = {
        "items": [
            {
                "relative_path": "ok/one.pdf",
                "status": "success",
                "overall_risk": "low",
                "domain_risks": {"D1": "low", "D2": "some concerns", "D3": "high"},
            },
            {
                "relative_path": "skip/two.pdf",
                "status": "skipped",
                "overall_risk": "high",
                "domain_risks": {},
            },
            {
                "relative_path": "bad/three.pdf",
                "status": "failed",
                "overall_risk": None,
                "domain_risks": {},
            },
        ]
    }

    rows = build_traffic_light_rows(summary)
    assert [row.label for row in rows] == ["ok/one", "skip/two"]
    assert rows[0].risks["D2"] == "some_concerns"


def test_generate_batch_traffic_light_png_creates_file(tmp_path: Path) -> None:
    summary = {
        "items": [
            {
                "relative_path": "paper-a.pdf",
                "status": "success",
                "overall_risk": "low",
                "domain_risks": {
                    "D1": "low",
                    "D2": "some_concerns",
                    "D3": "high",
                    "D4": "low",
                    "D5": "low",
                },
            }
        ]
    }

    output_path = tmp_path / "plot.png"
    count = generate_batch_traffic_light_png(summary, output_path)

    assert count == 1
    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
