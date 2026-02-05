"""Batch run commands."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

from cli.common import (
    build_options,
    emit_json,
    load_options_payload,
    write_run_output_dir,
)
from core.config import get_settings
from persistence.hashing import hash_payload
from persistence.sqlite_store import SqliteStore
from reporting.batch_plot import (
    DEFAULT_BATCH_PLOT_FILE,
    SUMMARY_FILE_NAME,
    generate_batch_traffic_light_png,
    load_batch_summary,
)
from schemas.requests import Rob2Input
from services.rob2_runner import run_rob2


app = typer.Typer(
    help="批量运行 ROB2",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


_CHECKPOINT_VERSION = 1
_CHECKPOINT_FILE = "batch_checkpoint.json"
_SUMMARY_JSON_FILE = SUMMARY_FILE_NAME
_SUMMARY_CSV_FILE = "batch_summary.csv"
_BATCH_PLOT_FILE = DEFAULT_BATCH_PLOT_FILE
_CSV_COLUMNS = [
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


@app.command("run", help="批量运行目录中的 PDF")
def run_batch(
    input_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        metavar="目录路径",
    ),
    output_dir: Path = typer.Option(
        Path("results/batch"),
        "--output-dir",
        help="批量输出目录（默认: ./results/batch）",
    ),
    options: str | None = typer.Option(
        None,
        "--options",
        help="Rob2RunOptions 的 JSON 字符串",
    ),
    options_file: Path | None = typer.Option(
        None,
        "--options-file",
        help="包含 Rob2RunOptions 的 JSON/YAML 文件路径",
    ),
    set_values: list[str] | None = typer.Option(
        None,
        "--set",
        help="使用 key=value 覆盖单个选项，可重复传入",
    ),
    batch_id: str | None = typer.Option(
        None,
        "--batch-id",
        help="绑定已有批次 ID",
    ),
    batch_name: str | None = typer.Option(
        None,
        "--batch-name",
        help="显式创建批次并绑定（仅当未传 --batch-id）",
    ),
    json_out: bool = typer.Option(
        False,
        "--json",
        help="输出批量汇总 JSON",
    ),
    table: bool = typer.Option(
        True,
        "--table/--no-table",
        help="每文件输出 ROB2 Markdown 表格",
    ),
    html: bool = typer.Option(
        False,
        "--html",
        help="每文件生成交互式 HTML 报告",
    ),
    docx: bool = typer.Option(
        False,
        "--docx",
        help="每文件生成 Word 报告",
    ),
    pdf: bool = typer.Option(
        False,
        "--pdf",
        help="每文件生成 PDF 报告",
    ),
    reset: bool = typer.Option(
        False,
        "--reset",
        help="忽略历史 checkpoint 并重建批次执行状态",
    ),
    persist: bool = typer.Option(
        True,
        "--persist/--no-persist",
        help="写入持久化运行记录与分析包",
    ),
    persist_dir: Path | None = typer.Option(
        None,
        "--persist-dir",
        help="持久化根目录（默认使用配置项）",
    ),
    persist_scope: str | None = typer.Option(
        None,
        "--persist-scope",
        help="持久化范围（analysis 等）",
    ),
    cache_dir: Path | None = typer.Option(
        None,
        "--cache-dir",
        help="缓存根目录（默认使用配置项）",
    ),
    cache_scope: str | None = typer.Option(
        None,
        "--cache-scope",
        help="缓存范围（deterministic|none）",
    ),
    plot: bool = typer.Option(
        True,
        "--plot/--no-plot",
        help="批量结束后生成红绿灯图（PNG）",
    ),
    plot_output: Path | None = typer.Option(
        None,
        "--plot-output",
        help="红绿灯图输出路径（默认: <output-dir>/batch_traffic_light.png）",
    ),
) -> None:
    input_dir_abs = input_dir.resolve()
    output_dir_abs = output_dir.resolve()

    _ensure_output_dir_writable(output_dir_abs)

    pdf_files = _discover_pdfs(input_dir_abs)
    if not pdf_files:
        raise typer.BadParameter(f"目录中未发现 PDF: {input_dir_abs}")

    relative_paths = [path.relative_to(input_dir_abs).as_posix() for path in pdf_files]
    file_list_hash = hash_payload(relative_paths)

    payload = load_options_payload(options, options_file, set_values)
    options_obj = build_options(payload)

    settings = get_settings()
    resolved_persistence_dir = str(persist_dir) if persist_dir else settings.persistence_dir
    resolved_persist_scope = persist_scope or settings.persistence_scope
    resolved_cache_dir = str(cache_dir) if cache_dir else settings.cache_dir
    resolved_cache_scope = cache_scope or settings.cache_scope

    options_hash = hash_payload(
        {
            "payload": payload,
            "table": table,
            "html": html,
            "docx": docx,
            "pdf": pdf,
            "persist": persist,
            "persist_dir": resolved_persistence_dir,
            "persist_scope": resolved_persist_scope,
            "cache_dir": resolved_cache_dir,
            "cache_scope": resolved_cache_scope,
        }
    )

    checkpoint_path = output_dir_abs / _CHECKPOINT_FILE
    checkpoint: dict[str, Any]

    if checkpoint_path.exists() and not reset:
        checkpoint = _load_checkpoint(checkpoint_path)
        _assert_checkpoint_compatible(
            checkpoint,
            input_dir_abs=str(input_dir_abs),
            output_dir_abs=str(output_dir_abs),
            options_hash=options_hash,
            file_list_hash=file_list_hash,
            batch_id=batch_id,
            batch_name=batch_name,
        )
    else:
        checkpoint = _build_initial_checkpoint(
            input_dir_abs=str(input_dir_abs),
            output_dir_abs=str(output_dir_abs),
            options_hash=options_hash,
            file_list_hash=file_list_hash,
            batch_id=batch_id,
            batch_name=batch_name,
            relative_paths=relative_paths,
        )

    effective_batch_id = _resolve_batch_id(
        checkpoint=checkpoint,
        explicit_batch_id=batch_id,
        explicit_batch_name=batch_name,
        persist_enabled=persist,
        persistence_dir=resolved_persistence_dir,
    )
    checkpoint["batch_id"] = effective_batch_id
    if batch_name is not None:
        checkpoint["batch_name"] = batch_name

    _write_checkpoint(checkpoint_path, checkpoint)
    _write_summary_files(checkpoint, output_dir_abs)

    items = {item["relative_path"]: item for item in checkpoint["items"]}
    missing_items = [path for path in relative_paths if path not in items]
    if missing_items:
        raise typer.BadParameter(
            "checkpoint 缺少文件条目，请使用 --reset 重新执行。"
        )
    total = len(relative_paths)

    for index, (rel_path, pdf_path) in enumerate(zip(relative_paths, pdf_files), start=1):
        item = items[rel_path]
        subdir = output_dir_abs / str(item["output_subdir"])
        result_file = subdir / "result.json"

        if item.get("status") in {"success", "skipped"} and result_file.exists():
            item["status"] = "skipped"
            item["updated_at"] = _now_iso()
            _write_checkpoint(checkpoint_path, checkpoint)
            _write_summary_files(checkpoint, output_dir_abs)
            typer.echo(f"[{index}/{total}] skip {rel_path}")
            continue

        item["status"] = "running"
        item["error"] = None
        item["updated_at"] = _now_iso()
        _write_checkpoint(checkpoint_path, checkpoint)

        typer.echo(f"[{index}/{total}] run {rel_path}")
        try:
            result = run_rob2(
                Rob2Input(pdf_path=str(pdf_path)),
                options_obj,
                persist_enabled=persist,
                persistence_dir=resolved_persistence_dir,
                persistence_scope=resolved_persist_scope,
                cache_dir=resolved_cache_dir,
                cache_scope=resolved_cache_scope,
                batch_id=effective_batch_id,
            )
            write_run_output_dir(
                result,
                subdir,
                include_table=table,
                html=html,
                docx=docx,
                pdf=pdf,
                pdf_name=pdf_path.name,
            )
            domain_risks = {
                str(domain.domain): domain.risk for domain in result.result.domains
            }
            item["status"] = "success"
            item["run_id"] = result.run_id
            item["runtime_ms"] = result.runtime_ms
            item["overall_risk"] = result.result.overall.risk
            item["domain_risks"] = domain_risks
            item["error"] = None
        except Exception as exc:  # pragma: no cover - exercised via integration tests
            item["status"] = "failed"
            item["error"] = _format_error(exc)
            item["run_id"] = None
            item["runtime_ms"] = None
            item["overall_risk"] = None
            item["domain_risks"] = {}
        finally:
            item["updated_at"] = _now_iso()
            _write_checkpoint(checkpoint_path, checkpoint)
            _write_summary_files(checkpoint, output_dir_abs)

    summary = _build_summary_payload(checkpoint)
    if plot:
        if plot_output is None:
            resolved_plot_output = output_dir_abs / _BATCH_PLOT_FILE
        else:
            resolved_plot_output = plot_output.resolve()
        try:
            plotted = _generate_batch_plot(
                summary,
                resolved_plot_output,
                include_non_success=False,
            )
            typer.echo(f"已写入: {resolved_plot_output} (rows={plotted})")
        except Exception as exc:  # pragma: no cover - defensive
            typer.echo(f"Warning: 红绿灯图生成失败: {exc}")

    if json_out:
        emit_json(summary)

    failed = summary.get("counts", {}).get("failed", 0)
    if failed:
        raise typer.Exit(code=1)


@app.command("plot", help="根据批量 summary 绘制红绿灯图（PNG）")
def plot_batch(
    source: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=True,
        readable=True,
        metavar="目录或summary路径",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="输出图片路径（默认: <batch-output-dir>/batch_traffic_light.png）",
    ),
    include_non_success: bool = typer.Option(
        False,
        "--include-non-success/--no-include-non-success",
        help="将 failed/pending/running 条目以灰色占位纳入图中",
    ),
) -> None:
    summary_path, default_output = _resolve_summary_input(source.resolve())
    summary = _load_summary_or_raise(summary_path)
    output_path = output.resolve() if output is not None else default_output
    plotted = _generate_batch_plot(
        summary,
        output_path,
        include_non_success=include_non_success,
    )
    typer.echo(f"已写入: {output_path} (rows={plotted})")


def _build_initial_checkpoint(
    *,
    input_dir_abs: str,
    output_dir_abs: str,
    options_hash: str,
    file_list_hash: str,
    batch_id: str | None,
    batch_name: str | None,
    relative_paths: list[str],
) -> dict[str, Any]:
    items = []
    for rel_path in relative_paths:
        output_subdir = str(Path(rel_path).with_suffix(""))
        items.append(
            {
                "relative_path": rel_path,
                "output_subdir": output_subdir,
                "status": "pending",
                "run_id": None,
                "runtime_ms": None,
                "overall_risk": None,
                "domain_risks": {},
                "error": None,
                "updated_at": _now_iso(),
            }
        )

    return {
        "version": _CHECKPOINT_VERSION,
        "input_dir_abs": input_dir_abs,
        "output_dir_abs": output_dir_abs,
        "options_hash": options_hash,
        "file_list_hash": file_list_hash,
        "batch_id": batch_id,
        "batch_name": batch_name,
        "items": items,
    }


def _load_checkpoint(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise typer.BadParameter(f"checkpoint 读取失败: {path} ({exc})") from exc

    if not isinstance(data, dict):
        raise typer.BadParameter(f"checkpoint 格式错误: {path}")
    if not isinstance(data.get("items"), list):
        raise typer.BadParameter(f"checkpoint items 缺失: {path}")
    return data


def _assert_checkpoint_compatible(
    checkpoint: dict[str, Any],
    *,
    input_dir_abs: str,
    output_dir_abs: str,
    options_hash: str,
    file_list_hash: str,
    batch_id: str | None,
    batch_name: str | None,
) -> None:
    errors: list[str] = []
    if checkpoint.get("input_dir_abs") != input_dir_abs:
        errors.append("input_dir_abs")
    if checkpoint.get("output_dir_abs") != output_dir_abs:
        errors.append("output_dir_abs")
    if checkpoint.get("options_hash") != options_hash:
        errors.append("options_hash")
    if checkpoint.get("file_list_hash") != file_list_hash:
        errors.append("file_list_hash")
    if batch_id is not None and checkpoint.get("batch_id") not in {None, batch_id}:
        errors.append("batch_id")
    if (
        batch_id is None
        and batch_name is not None
        and checkpoint.get("batch_name") not in {None, batch_name}
    ):
        errors.append("batch_name")

    if errors:
        joined = ", ".join(errors)
        raise typer.BadParameter(
            f"checkpoint 与当前参数不一致: {joined}。请使用 --reset 重新执行。"
        )


def _resolve_batch_id(
    *,
    checkpoint: dict[str, Any],
    explicit_batch_id: str | None,
    explicit_batch_name: str | None,
    persist_enabled: bool,
    persistence_dir: str,
) -> str | None:
    if explicit_batch_id:
        return explicit_batch_id

    existing = checkpoint.get("batch_id")
    if isinstance(existing, str) and existing.strip():
        return existing.strip()

    if not explicit_batch_name:
        return None

    if not persist_enabled:
        raise typer.BadParameter("--batch-name 需要持久化开启（不要使用 --no-persist）")

    store = SqliteStore(Path(persistence_dir) / "metadata.sqlite")
    record = store.create_batch(name=explicit_batch_name, metadata=None)
    return record.batch_id


def _discover_pdfs(input_dir: Path) -> list[Path]:
    files = [
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    ]
    files.sort(key=lambda path: path.relative_to(input_dir).as_posix())
    return files


def _ensure_output_dir_writable(output_dir: Path) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        probe = output_dir / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:  # pragma: no cover - platform-dependent
        raise typer.BadParameter(f"输出目录不可写: {output_dir} ({exc})") from exc


def _write_checkpoint(path: Path, payload: dict[str, Any]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _build_summary_payload(checkpoint: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = list(checkpoint.get("items") or [])
    counts = {
        "total": len(items),
        "pending": 0,
        "running": 0,
        "success": 0,
        "failed": 0,
        "skipped": 0,
    }
    for item in items:
        status = str(item.get("status") or "pending")
        if status in counts:
            counts[status] += 1

    return {
        "version": checkpoint.get("version"),
        "input_dir_abs": checkpoint.get("input_dir_abs"),
        "output_dir_abs": checkpoint.get("output_dir_abs"),
        "batch_id": checkpoint.get("batch_id"),
        "batch_name": checkpoint.get("batch_name"),
        "counts": counts,
        "items": sorted(items, key=lambda item: str(item.get("relative_path") or "")),
    }


def _write_summary_files(checkpoint: dict[str, Any], output_dir: Path) -> None:
    summary = _build_summary_payload(checkpoint)

    (output_dir / _SUMMARY_JSON_FILE).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with (output_dir / _SUMMARY_CSV_FILE).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_COLUMNS)
        writer.writeheader()
        for item in summary["items"]:
            domain_risks = item.get("domain_risks") or {}
            row = {
                "relative_path": item.get("relative_path"),
                "status": item.get("status"),
                "run_id": item.get("run_id"),
                "runtime_ms": item.get("runtime_ms"),
                "overall_risk": item.get("overall_risk"),
                "D1_risk": domain_risks.get("D1"),
                "D2_risk": domain_risks.get("D2"),
                "D3_risk": domain_risks.get("D3"),
                "D4_risk": domain_risks.get("D4"),
                "D5_risk": domain_risks.get("D5"),
                "error": item.get("error"),
            }
            writer.writerow(row)


def _resolve_summary_input(source: Path) -> tuple[Path, Path]:
    if source.is_dir():
        summary_path = source / _SUMMARY_JSON_FILE
        output_path = source / _BATCH_PLOT_FILE
    else:
        summary_path = source
        output_path = source.parent / _BATCH_PLOT_FILE

    if not summary_path.exists():
        raise typer.BadParameter(f"summary 文件不存在: {summary_path}")
    if summary_path.is_dir():
        raise typer.BadParameter(f"summary 不是文件: {summary_path}")
    return summary_path, output_path


def _load_summary_or_raise(path: Path) -> dict[str, Any]:
    try:
        return load_batch_summary(path)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _generate_batch_plot(
    summary: dict[str, Any],
    output_path: Path,
    *,
    include_non_success: bool,
) -> int:
    try:
        return generate_batch_traffic_light_png(
            summary,
            output_path,
            include_non_success=include_non_success,
        )
    except ValueError as exc:
        raise typer.BadParameter(f"红绿灯图生成失败: {exc}") from exc


def _format_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["app"]
