from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
import typer

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
