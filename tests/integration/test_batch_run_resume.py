from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import typer
from typer.testing import CliRunner

from cli.commands import batch as batch_command


def test_batch_run_resumes_failed_items(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    (input_dir / "one.pdf").write_bytes(b"%PDF-1.4")
    (input_dir / "two.pdf").write_bytes(b"%PDF-1.4")

    output_dir = tmp_path / "out"

    mode = {"fail_two": True}
    calls: list[str] = []

    def fake_run_rob2(input_data, *_args, **_kwargs):
        name = Path(str(input_data.pdf_path)).name
        calls.append(name)
        if mode["fail_two"] and name == "two.pdf":
            raise RuntimeError("boom")

        domain = SimpleNamespace(domain="D1", risk="low")
        overall = SimpleNamespace(risk="low")
        result_payload = SimpleNamespace(overall=overall, domains=[domain])
        return SimpleNamespace(
            run_id=f"run_{name}",
            runtime_ms=42,
            result=result_payload,
        )

    def fake_write_run_output_dir(result, path, **_kwargs):
        path.mkdir(parents=True, exist_ok=True)
        (path / "result.json").write_text(
            json.dumps({"run_id": result.run_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    monkeypatch.setattr(batch_command, "run_rob2", fake_run_rob2)
    monkeypatch.setattr(batch_command, "write_run_output_dir", fake_write_run_output_dir)

    try:
        batch_command.run_batch(
            input_dir=input_dir,
            output_dir=output_dir,
            options=None,
            options_file=None,
            set_values=None,
            batch_id=None,
            batch_name=None,
            json_out=False,
            table=True,
            html=False,
            docx=False,
            pdf=False,
            reset=False,
            persist=False,
            persist_dir=None,
            persist_scope=None,
            cache_dir=None,
            cache_scope=None,
            plot=True,
            plot_output=None,
            excel=True,
            excel_output=None,
        )
    except typer.Exit as exc:
        assert exc.exit_code == 1
    else:
        raise AssertionError("expected partial-failure exit")

    summary_1 = json.loads((output_dir / "batch_summary.json").read_text(encoding="utf-8"))
    assert summary_1["counts"]["success"] == 1
    assert summary_1["counts"]["failed"] == 1
    assert (output_dir / "batch_traffic_light.png").exists()
    assert (output_dir / "batch_summary.xlsx").exists()

    mode["fail_two"] = False
    batch_command.run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        options=None,
        options_file=None,
        set_values=None,
        batch_id=None,
        batch_name=None,
        json_out=False,
        table=True,
        html=False,
        docx=False,
        pdf=False,
        reset=False,
        persist=False,
        persist_dir=None,
        persist_scope=None,
        cache_dir=None,
        cache_scope=None,
        plot=True,
        plot_output=None,
        excel=True,
        excel_output=None,
    )

    summary_2 = json.loads((output_dir / "batch_summary.json").read_text(encoding="utf-8"))
    assert summary_2["counts"]["failed"] == 0
    assert summary_2["counts"]["success"] == 1
    assert summary_2["counts"]["skipped"] == 1
    assert (output_dir / "batch_traffic_light.png").exists()
    assert (output_dir / "batch_summary.xlsx").exists()

    assert calls == ["one.pdf", "two.pdf", "two.pdf"]


def test_batch_run_no_plot_does_not_generate_png(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    (input_dir / "one.pdf").write_bytes(b"%PDF-1.4")

    output_dir = tmp_path / "out"

    def fake_run_rob2(input_data, *_args, **_kwargs):
        name = Path(str(input_data.pdf_path)).name
        domain = SimpleNamespace(domain="D1", risk="low")
        overall = SimpleNamespace(risk="low")
        result_payload = SimpleNamespace(overall=overall, domains=[domain])
        return SimpleNamespace(
            run_id=f"run_{name}",
            runtime_ms=42,
            result=result_payload,
        )

    def fake_write_run_output_dir(result, path, **_kwargs):
        path.mkdir(parents=True, exist_ok=True)
        (path / "result.json").write_text(
            json.dumps({"run_id": result.run_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    monkeypatch.setattr(batch_command, "run_rob2", fake_run_rob2)
    monkeypatch.setattr(batch_command, "write_run_output_dir", fake_write_run_output_dir)

    batch_command.run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        options=None,
        options_file=None,
        set_values=None,
        batch_id=None,
        batch_name=None,
        json_out=False,
        table=True,
        html=False,
        docx=False,
        pdf=False,
        reset=False,
        persist=False,
        persist_dir=None,
        persist_scope=None,
        cache_dir=None,
        cache_scope=None,
        plot=False,
        plot_output=None,
        excel=True,
        excel_output=None,
    )

    assert not (output_dir / "batch_traffic_light.png").exists()
    assert (output_dir / "batch_summary.xlsx").exists()


def test_batch_run_defaults_enable_all_report_formats(
    tmp_path: Path,
    monkeypatch,
) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    (input_dir / "one.pdf").write_bytes(b"%PDF-1.4")

    output_dir = tmp_path / "out"
    captured_kwargs: dict | None = None

    def fake_run_rob2(input_data, *_args, **_kwargs):
        name = Path(str(input_data.pdf_path)).name
        domain = SimpleNamespace(domain="D1", risk="low")
        overall = SimpleNamespace(risk="low")
        result_payload = SimpleNamespace(overall=overall, domains=[domain])
        return SimpleNamespace(
            run_id=f"run_{name}",
            runtime_ms=42,
            result=result_payload,
        )

    def fake_write_run_output_dir(result, path, **kwargs):
        nonlocal captured_kwargs
        captured_kwargs = kwargs
        path.mkdir(parents=True, exist_ok=True)
        (path / "result.json").write_text(
            json.dumps({"run_id": result.run_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    monkeypatch.setattr(batch_command, "run_rob2", fake_run_rob2)
    monkeypatch.setattr(batch_command, "write_run_output_dir", fake_write_run_output_dir)

    runner = CliRunner()
    result = runner.invoke(
        batch_command.app,
        [
            "run",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--no-persist",
            "--no-plot",
            "--no-excel",
        ],
    )
    assert result.exit_code == 0

    assert captured_kwargs is not None
    assert captured_kwargs["include_table"] is True
    assert captured_kwargs["html"] is True
    assert captured_kwargs["docx"] is True
    assert captured_kwargs["pdf"] is True


def test_batch_run_reuses_fixed_outputs_by_pdf_hash(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    (input_dir / "one.pdf").write_bytes(b"%PDF-1.4\none")
    (input_dir / "two.pdf").write_bytes(b"%PDF-1.4\ntwo")

    output_dir = tmp_path / "out"
    cached_dir = output_dir / "history" / "cached_one"
    cached_dir.mkdir(parents=True)

    one_hash = batch_command.sha256_file(input_dir / "one.pdf")
    (cached_dir / "result.json").write_text(
        json.dumps(
            {
                "run_id": "run_cached",
                "runtime_ms": 123,
                "result": {
                    "overall": {"risk": "low", "rationale": "cached"},
                    "domains": [{"domain": "D1", "risk": "low"}],
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (cached_dir / "report.html").write_text("<html>cached</html>", encoding="utf-8")
    (cached_dir / "batch_item_meta.json").write_text(
        json.dumps(
            {
                "version": 1,
                "pdf_sha256": one_hash,
                "relative_path": "legacy/one.pdf",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    calls: list[str] = []

    def fake_run_rob2(input_data, *_args, **_kwargs):
        name = Path(str(input_data.pdf_path)).name
        calls.append(name)
        domain = SimpleNamespace(domain="D1", risk="high")
        overall = SimpleNamespace(risk="high")
        result_payload = SimpleNamespace(overall=overall, domains=[domain])
        return SimpleNamespace(
            run_id=f"run_{name}",
            runtime_ms=42,
            result=result_payload,
        )

    def fake_write_run_output_dir(result, path, **_kwargs):
        path.mkdir(parents=True, exist_ok=True)
        (path / "result.json").write_text(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "runtime_ms": result.runtime_ms,
                    "result": {
                        "variant": "standard",
                        "question_set_version": "1.0",
                        "overall": {"risk": result.result.overall.risk, "rationale": "ok"},
                        "domains": [
                            {
                                "domain": domain.domain,
                                "risk": domain.risk,
                            }
                            for domain in result.result.domains
                        ],
                        "citations": [],
                        "document_metadata": None,
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(batch_command, "run_rob2", fake_run_rob2)
    monkeypatch.setattr(batch_command, "write_run_output_dir", fake_write_run_output_dir)

    batch_command.run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        options=None,
        options_file=None,
        set_values=None,
        batch_id=None,
        batch_name=None,
        json_out=False,
        table=True,
        html=False,
        docx=False,
        pdf=False,
        reset=False,
        persist=False,
        persist_dir=None,
        persist_scope=None,
        cache_dir=None,
        cache_scope=None,
        plot=True,
        plot_output=None,
        excel=True,
        excel_output=None,
    )

    assert calls == ["two.pdf"]

    summary = json.loads((output_dir / "batch_summary.json").read_text(encoding="utf-8"))
    assert summary["counts"]["success"] == 1
    assert summary["counts"]["skipped"] == 1
    assert summary["counts"]["failed"] == 0

    by_rel = {item["relative_path"]: item for item in summary["items"]}
    assert by_rel["one.pdf"]["status"] == "skipped"
    assert by_rel["one.pdf"]["run_id"] == "run_cached"

    reused_result = json.loads((output_dir / "one" / "result.json").read_text(encoding="utf-8"))
    assert reused_result["run_id"] == "run_cached"
    assert (output_dir / "one" / "batch_item_meta.json").exists()
    assert (output_dir / "batch_traffic_light.png").exists()
    assert (output_dir / "batch_summary.xlsx").exists()


def test_batch_run_does_not_reuse_without_batch_meta(tmp_path: Path, monkeypatch) -> None:
    input_dir = tmp_path / "pdfs"
    input_dir.mkdir()
    (input_dir / "one.pdf").write_bytes(b"%PDF-1.4\none")

    output_dir = tmp_path / "out"
    preexisting = output_dir / "one"
    preexisting.mkdir(parents=True)
    (preexisting / "result.json").write_text(
        json.dumps(
            {
                "run_id": "run_old",
                "runtime_ms": 1,
                "result": {"overall": {"risk": "low"}, "domains": []},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    calls: list[str] = []

    def fake_run_rob2(input_data, *_args, **_kwargs):
        calls.append(Path(str(input_data.pdf_path)).name)
        domain = SimpleNamespace(domain="D1", risk="low")
        overall = SimpleNamespace(risk="low")
        result_payload = SimpleNamespace(overall=overall, domains=[domain])
        return SimpleNamespace(
            run_id="run_new",
            runtime_ms=55,
            result=result_payload,
        )

    def fake_write_run_output_dir(result, path, **_kwargs):
        path.mkdir(parents=True, exist_ok=True)
        (path / "result.json").write_text(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "runtime_ms": result.runtime_ms,
                    "result": {
                        "overall": {"risk": result.result.overall.risk},
                        "domains": [{"domain": "D1", "risk": "low"}],
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(batch_command, "run_rob2", fake_run_rob2)
    monkeypatch.setattr(batch_command, "write_run_output_dir", fake_write_run_output_dir)

    batch_command.run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        options=None,
        options_file=None,
        set_values=None,
        batch_id=None,
        batch_name=None,
        json_out=False,
        table=True,
        html=False,
        docx=False,
        pdf=False,
        reset=False,
        persist=False,
        persist_dir=None,
        persist_scope=None,
        cache_dir=None,
        cache_scope=None,
        plot=False,
        plot_output=None,
        excel=False,
        excel_output=None,
    )

    assert calls == ["one.pdf"]
