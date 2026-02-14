from __future__ import annotations

from pathlib import Path

import reporting.batch_plot as batch_plot
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


def test_generate_batch_traffic_light_png_supports_chinese_label(tmp_path: Path) -> None:
    summary = {
        "items": [
            {
                "relative_path": "样本/研究一.pdf",
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

    output_path = tmp_path / "plot-zh.png"
    count = generate_batch_traffic_light_png(summary, output_path)

    assert count == 1
    assert output_path.exists()


def test_load_plot_font_prefers_env_var(monkeypatch) -> None:
    sentinel = object()
    env_path = "/tmp/custom-cjk-font.ttf"
    calls: list[Path] = []

    def fake_loader(path: Path, size: int) -> object | None:
        assert size == 14
        calls.append(path)
        if str(path) == env_path:
            return sentinel
        return None

    monkeypatch.setenv("ROB2_BATCH_PLOT_FONT_PATH", env_path)
    monkeypatch.setattr(batch_plot, "_load_truetype_font", fake_loader)

    font = batch_plot._load_plot_font(14)
    assert font is sentinel
    assert calls == [Path(env_path)]


def test_load_plot_font_scans_candidates_when_env_missing(monkeypatch) -> None:
    sentinel = object()
    calls: list[Path] = []
    candidates = ("/missing-font.ttf", "/available-font.ttf")

    def fake_loader(path: Path, size: int) -> object | None:
        assert size == 12
        calls.append(path)
        if str(path) == candidates[1]:
            return sentinel
        return None

    monkeypatch.delenv("ROB2_BATCH_PLOT_FONT_PATH", raising=False)
    monkeypatch.setattr(batch_plot, "_FONT_CANDIDATES", candidates)
    monkeypatch.setattr(batch_plot, "_load_truetype_font", fake_loader)

    font = batch_plot._load_plot_font(12)
    assert font is sentinel
    assert calls == [Path(candidates[0]), Path(candidates[1])]


def test_draw_matrix_legend_excludes_not_applicable_label(monkeypatch) -> None:
    rows = [
        batch_plot.TrafficLightRow(
            label="paper-a",
            status="success",
            risks={
                "overall": "low",
                "D1": "low",
                "D2": "some_concerns",
                "D3": "high",
                "D4": "not_applicable",
                "D5": "low",
            },
        )
    ]
    drawn_texts: list[str] = []
    original_draw_text = batch_plot._draw_text

    def spy_draw_text(draw, position, text, *, fill, font):
        drawn_texts.append(text)
        return original_draw_text(draw, position, text, fill=fill, font=font)

    monkeypatch.setattr(batch_plot, "_draw_text", spy_draw_text)

    batch_plot._draw_matrix(rows)

    assert "N/A" not in drawn_texts
