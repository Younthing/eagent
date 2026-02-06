from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import typer
from openpyxl import load_workbook

from cli.commands import batch as batch_command


def test_discover_pdfs_recursively_sorted(tmp_path: Path) -> None:
    (tmp_path / "b").mkdir()
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.PDF").write_bytes(b"%PDF-1.4")
    (tmp_path / "b" / "y.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "z.txt").write_text("ignore", encoding="utf-8")

    files = batch_command._discover_pdfs(tmp_path)
    rel = [item.relative_to(tmp_path).as_posix() for item in files]

    assert rel == ["a/x.PDF", "b/y.pdf"]


def test_checkpoint_compatibility_requires_reset() -> None:
    checkpoint = {
        "input_dir_abs": "/input",
        "output_dir_abs": "/out",
        "options_hash": "old",
        "file_list_hash": "same",
        "batch_id": None,
        "batch_name": None,
        "items": [],
    }

    with pytest.raises(typer.BadParameter):
        batch_command._assert_checkpoint_compatible(
            checkpoint,
            input_dir_abs="/input",
            output_dir_abs="/out",
            options_hash="new",
            file_list_hash="same",
            batch_id=None,
            batch_name=None,
        )


def test_checkpoint_compatibility_ignores_batch_name_when_batch_id_provided() -> None:
    checkpoint = {
        "input_dir_abs": "/input",
        "output_dir_abs": "/out",
        "options_hash": "same",
        "file_list_hash": "same",
        "batch_id": "batch_1",
        "batch_name": "old_name",
        "items": [],
    }

    batch_command._assert_checkpoint_compatible(
        checkpoint,
        input_dir_abs="/input",
        output_dir_abs="/out",
        options_hash="same",
        file_list_hash="same",
        batch_id="batch_1",
        batch_name="new_name",
    )


def test_write_summary_files_contains_expected_columns(tmp_path: Path) -> None:
    checkpoint = {
        "version": 1,
        "input_dir_abs": "/input",
        "output_dir_abs": "/out",
        "batch_id": "batch_1",
        "batch_name": "nightly",
        "items": [
            {
                "relative_path": "a/paper.pdf",
                "output_subdir": "a/paper",
                "status": "success",
                "run_id": "run_1",
                "runtime_ms": 123,
                "overall_risk": "low",
                "domain_risks": {
                    "D1": "low",
                    "D2": "low",
                    "D3": "some concerns",
                    "D4": "low",
                    "D5": "low",
                },
                "error": None,
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ],
    }

    batch_command._write_summary_files(checkpoint, tmp_path)

    summary = json.loads((tmp_path / "batch_summary.json").read_text(encoding="utf-8"))
    assert summary["counts"]["success"] == 1

    with (tmp_path / "batch_summary.csv").open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    assert reader.fieldnames == [
        "relative_path",
        "status",
        "run_id",
        "runtime_ms",
        "overall_risk",
        "D1_risk",
        "D2_risk",
        "D3_risk",
        "D4_risk",
        "D5_risk",
        "error",
    ]
    assert len(rows) == 1
    assert rows[0]["relative_path"] == "a/paper.pdf"
    assert rows[0]["D3_risk"] == "some concerns"


def test_plot_batch_accepts_directory_source(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    summary = {
        "items": [
            {
                "relative_path": "a/paper.pdf",
                "status": "success",
                "overall_risk": "low",
                "domain_risks": {
                    "D1": "low",
                    "D2": "some concerns",
                    "D3": "high",
                    "D4": "low",
                    "D5": "low",
                },
            }
        ]
    }
    (batch_dir / "batch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    batch_command.plot_batch(
        source=batch_dir,
        output=None,
        include_non_success=False,
    )

    image_path = batch_dir / "batch_traffic_light.png"
    assert image_path.exists()
    assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_plot_batch_accepts_summary_file_source(tmp_path: Path) -> None:
    summary_path = tmp_path / "batch_summary.json"
    summary = {
        "items": [
            {
                "relative_path": "a/paper.pdf",
                "status": "success",
                "overall_risk": "high",
                "domain_risks": {
                    "D1": "high",
                    "D2": "some_concerns",
                    "D3": "low",
                    "D4": "low",
                    "D5": "low",
                },
            }
        ]
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    output = tmp_path / "custom_plot.png"
    batch_command.plot_batch(
        source=summary_path,
        output=output,
        include_non_success=False,
    )

    assert output.exists()
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_plot_batch_raises_when_no_plot_rows(tmp_path: Path) -> None:
    summary_path = tmp_path / "batch_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "relative_path": "a/paper.pdf",
                        "status": "failed",
                        "overall_risk": None,
                        "domain_risks": {},
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with pytest.raises(typer.BadParameter, match="红绿灯图生成失败"):
        batch_command.plot_batch(
            source=summary_path,
            output=None,
            include_non_success=False,
        )


def test_excel_batch_accepts_directory_source(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    summary = {
        "output_dir_abs": str(batch_dir),
        "items": [
            {
                "relative_path": "a/paper.pdf",
                "status": "success",
                "run_id": "run_1",
                "runtime_ms": 123,
                "overall_risk": "low",
                "domain_risks": {"D1": "low"},
                "error": None,
            }
        ],
    }
    (batch_dir / "batch_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result_path = batch_dir / "a" / "paper" / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(
            {
                "run_id": "run_1",
                "result": {
                    "variant": "standard",
                    "question_set_version": "1.0",
                    "overall": {"risk": "low", "rationale": "ok"},
                    "domains": [],
                    "citations": [],
                    "document_metadata": None,
                },
                "audit_reports": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    batch_command.excel_batch(source=batch_dir, output=None)

    excel_path = batch_dir / "batch_summary.xlsx"
    assert excel_path.exists()
    workbook = load_workbook(excel_path)
    assert "00_批次总览" in workbook.sheetnames


def test_excel_batch_accepts_summary_file_source(tmp_path: Path) -> None:
    summary_path = tmp_path / "batch_summary.json"
    summary = {
        "output_dir_abs": str(tmp_path),
        "items": [
            {
                "relative_path": "paper.pdf",
                "status": "failed",
                "run_id": None,
                "runtime_ms": None,
                "overall_risk": None,
                "domain_risks": {},
                "error": "boom",
            }
        ],
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    output = tmp_path / "custom_summary.xlsx"
    batch_command.excel_batch(source=summary_path, output=output)

    assert output.exists()
    workbook = load_workbook(output)
    assert "00_批次总览" in workbook.sheetnames
