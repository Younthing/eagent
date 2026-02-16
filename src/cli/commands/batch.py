"""Batch run commands."""

from __future__ import annotations

import csv
import json
import os
import shutil
from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import sleep
from typing import Any, Literal

import typer

from cli.common import (
    build_options,
    emit_json,
    load_options_payload,
    write_run_output_dir,
)
from core.config import get_settings
from persistence.hashing import hash_payload, sha256_file
from persistence.sqlite_store import SqliteStore
from reporting.batch_plot import (
    DEFAULT_BATCH_PLOT_FILE,
    SUMMARY_FILE_NAME,
    generate_batch_traffic_light_png,
    load_batch_summary,
)
from reporting.batch_excel import (
    DEFAULT_BATCH_EXCEL_FILE,
    generate_batch_summary_excel,
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


_CHECKPOINT_VERSION = 2
_CHECKPOINT_FILE = "batch_checkpoint.json"
_SUMMARY_JSON_FILE = SUMMARY_FILE_NAME
_SUMMARY_CSV_FILE = "batch_summary.csv"
_BATCH_PLOT_FILE = DEFAULT_BATCH_PLOT_FILE
_BATCH_EXCEL_FILE = DEFAULT_BATCH_EXCEL_FILE
_BATCH_ITEM_META_VERSION = 1
_BATCH_ITEM_META_FILE = "batch_item_meta.json"
_MANAGED_RESULT_FILES = (
    "result.json",
    "table.md",
    "report.html",
    "report.docx",
    "report.pdf",
    "reports.json",
    "audit_reports.json",
    "debug.json",
    _BATCH_ITEM_META_FILE,
)
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

_RETRYABLE_ERROR_HINTS = (
    "429",
    "rate limit",
    "too many requests",
    "timeout",
    "timed out",
    "connecttimeout",
    "readtimeout",
    "temporarily unavailable",
)
_ADAPTIVE_SUCCESS_WINDOW = 3
_DEFAULT_RETRY_BACKOFF_MS = 800

_PROCESS_POOL_EXECUTOR = ProcessPoolExecutor


@dataclass(slots=True)
class _BatchTask:
    index: int
    total: int
    relative_path: str
    pdf_path: str
    pdf_sha256: str
    output_subdir: str
    batch_output_dir: str
    pdf_name: str
    options_payload: dict[str, Any]
    include_table: bool
    html: bool
    docx: bool
    pdf: bool
    persist_enabled: bool
    persistence_dir: str
    persistence_scope: str
    cache_dir: str
    cache_scope: str
    batch_id: str | None
    retry_429_max: int
    retry_429_backoff_ms: int


@dataclass(slots=True)
class _AdaptiveConcurrencyController:
    mode: Literal["adaptive", "fixed"]
    current_limit: int
    min_limit: int
    max_limit: int
    success_window: int = _ADAPTIVE_SUCCESS_WINDOW
    _success_streak: int = 0

    def __post_init__(self) -> None:
        self.current_limit = max(self.min_limit, min(self.current_limit, self.max_limit))
        self.success_window = max(1, int(self.success_window))
        self._success_streak = 0

    def observe(self, *, success: bool, had_retryable_error: bool) -> None:
        if self.mode == "fixed":
            return

        if had_retryable_error:
            self.current_limit = max(self.min_limit, self.current_limit - 1)
            self._success_streak = 0
            return

        if success:
            self._success_streak += 1
            if self._success_streak >= self.success_window:
                if self.current_limit < self.max_limit:
                    self.current_limit += 1
                self._success_streak = 0
            return

        self._success_streak = 0


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
        True,
        "--html/--no-html",
        help="每文件生成交互式 HTML 报告（默认开启）",
    ),
    docx: bool = typer.Option(
        True,
        "--docx/--no-docx",
        help="每文件生成 Word 报告（默认开启）",
    ),
    pdf: bool = typer.Option(
        True,
        "--pdf/--no-pdf",
        help="每文件生成 PDF 报告（默认开启）",
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
    excel: bool = typer.Option(
        True,
        "--excel/--no-excel",
        help="批量结束后生成 Excel 汇总（XLSX）",
    ),
    excel_output: Path | None = typer.Option(
        None,
        "--excel-output",
        help="Excel 汇总输出路径（默认: <output-dir>/batch_summary.xlsx）",
    ),
    workers: int | None = typer.Option(
        None,
        "--workers",
        min=1,
        help="并发 worker 数（默认使用配置或 CPU 自动值）",
    ),
    max_inflight_llm: int | None = typer.Option(
        None,
        "--max-inflight-llm",
        min=1,
        help="并发上限（用于并发控制）",
    ),
    rate_limit_mode: Literal["adaptive", "fixed"] | None = typer.Option(
        None,
        "--rate-limit-mode",
        help="限流模式（adaptive|fixed）",
    ),
    rate_limit_init: int | None = typer.Option(
        None,
        "--rate-limit-init",
        min=1,
        help="自适应限流初始并发额度",
    ),
    rate_limit_max: int | None = typer.Option(
        None,
        "--rate-limit-max",
        min=1,
        help="自适应限流最大并发额度",
    ),
    retry_429_max: int = typer.Option(
        4,
        "--retry-429-max",
        min=0,
        help="429/超时最大重试次数",
    ),
    retry_429_backoff_ms: int = typer.Option(
        _DEFAULT_RETRY_BACKOFF_MS,
        "--retry-429-backoff-ms",
        min=1,
        help="429/超时重试退避基值（毫秒）",
    ),
    prefetch: int | None = typer.Option(
        None,
        "--prefetch",
        min=1,
        help="任务预取长度（默认: workers*2）",
    ),
) -> None:
    input_dir_abs = input_dir.resolve()
    output_dir_abs = output_dir.resolve()

    _ensure_output_dir_writable(output_dir_abs)

    pdf_files = _discover_pdfs(input_dir_abs)
    if not pdf_files:
        raise typer.BadParameter(f"目录中未发现 PDF: {input_dir_abs}")

    file_entries = _build_file_entries(input_dir_abs, pdf_files)
    relative_paths = [str(entry["relative_path"]) for entry in file_entries]
    file_list_hash = _build_file_list_hash(file_entries)

    payload = load_options_payload(options, options_file, set_values)
    options_obj = build_options(payload)

    settings = get_settings()
    resolved_persistence_dir = str(persist_dir) if persist_dir else settings.persistence_dir
    resolved_persist_scope = persist_scope or settings.persistence_scope
    resolved_cache_dir = str(cache_dir) if cache_dir else settings.cache_dir
    resolved_cache_scope = cache_scope or settings.cache_scope
    resolved_workers = _resolve_workers(workers, getattr(settings, "batch_workers", None))
    resolved_max_inflight_llm = _resolve_int_with_default(
        max_inflight_llm,
        getattr(settings, "max_inflight_llm", None),
        fallback=max(1, resolved_workers),
    )
    if resolved_max_inflight_llm < 1:
        raise typer.BadParameter("--max-inflight-llm 必须 >= 1")

    resolved_rate_limit_mode = _resolve_rate_limit_mode(
        rate_limit_mode,
        getattr(settings, "rate_limit_mode", None),
    )
    resolved_rate_limit_init = _resolve_int_with_default(
        rate_limit_init,
        getattr(settings, "rate_limit_init", None),
        fallback=min(resolved_workers, resolved_max_inflight_llm),
    )
    resolved_rate_limit_max = _resolve_int_with_default(
        rate_limit_max,
        getattr(settings, "rate_limit_max", None),
        fallback=resolved_max_inflight_llm,
    )
    resolved_rate_limit_init = max(1, min(resolved_rate_limit_init, resolved_workers))
    resolved_rate_limit_max = max(1, min(resolved_rate_limit_max, resolved_workers))
    if resolved_rate_limit_init > resolved_rate_limit_max:
        resolved_rate_limit_init = resolved_rate_limit_max

    resolved_prefetch = max(1, prefetch if prefetch is not None else resolved_workers * 2)

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
            "workers": resolved_workers,
            "max_inflight_llm": resolved_max_inflight_llm,
            "rate_limit_mode": resolved_rate_limit_mode,
            "rate_limit_init": resolved_rate_limit_init,
            "rate_limit_max": resolved_rate_limit_max,
            "retry_429_max": retry_429_max,
            "retry_429_backoff_ms": retry_429_backoff_ms,
            "prefetch": resolved_prefetch,
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
            file_entries=file_entries,
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
    reusable_by_hash = _build_reusable_result_index(output_dir_abs)
    total = len(relative_paths)
    _ensure_runtime_meta(
        checkpoint,
        workers=resolved_workers,
        max_inflight_llm=resolved_max_inflight_llm,
        rate_limit_mode=resolved_rate_limit_mode,
    )

    run_tasks: deque[_BatchTask] = deque()
    options_payload = options_obj.model_dump()

    for index, entry in enumerate(file_entries, start=1):
        rel_path = str(entry["relative_path"])
        pdf_path = Path(str(entry["pdf_path"]))
        pdf_sha256 = str(entry["pdf_sha256"])
        item = items[rel_path]
        subdir = output_dir_abs / str(item["output_subdir"])
        result_file = subdir / "result.json"

        if item.get("status") in {"success", "skipped"} and result_file.exists():
            _write_batch_item_meta(
                output_dir=subdir,
                pdf_sha256=pdf_sha256,
                relative_path=rel_path,
            )
            item["status"] = "skipped"
            item["updated_at"] = _now_iso()
            reusable_by_hash[pdf_sha256] = subdir.resolve()
            _increment_runtime_meta(checkpoint, completed=1)
            _write_checkpoint(checkpoint_path, checkpoint)
            _write_summary_files(checkpoint, output_dir_abs)
            typer.echo(f"[{index}/{total}] skip {rel_path}")
            continue

        reusable_dir = reusable_by_hash.get(pdf_sha256)
        if reusable_dir is not None:
            _materialize_reused_output(source_dir=reusable_dir, target_dir=subdir)
            reused_summary = _read_result_summary(result_file)
            if reused_summary is not None:
                _write_batch_item_meta(
                    output_dir=subdir,
                    pdf_sha256=pdf_sha256,
                    relative_path=rel_path,
                )
                item["status"] = "skipped"
                item["run_id"] = reused_summary["run_id"]
                item["runtime_ms"] = reused_summary["runtime_ms"]
                item["overall_risk"] = reused_summary["overall_risk"]
                item["domain_risks"] = reused_summary["domain_risks"]
                item["error"] = None
                item["updated_at"] = _now_iso()
                reusable_by_hash[pdf_sha256] = subdir.resolve()
                _increment_runtime_meta(checkpoint, completed=1)
                _write_checkpoint(checkpoint_path, checkpoint)
                _write_summary_files(checkpoint, output_dir_abs)
                typer.echo(f"[{index}/{total}] skip {rel_path} (hash)")
                continue

        run_tasks.append(
            _BatchTask(
                index=index,
                total=total,
                relative_path=rel_path,
                pdf_path=str(pdf_path),
                pdf_sha256=pdf_sha256,
                output_subdir=str(item["output_subdir"]),
                batch_output_dir=str(output_dir_abs),
                pdf_name=pdf_path.name,
                options_payload=options_payload,
                include_table=table,
                html=html,
                docx=docx,
                pdf=pdf,
                persist_enabled=persist,
                persistence_dir=resolved_persistence_dir,
                persistence_scope=resolved_persist_scope,
                cache_dir=resolved_cache_dir,
                cache_scope=resolved_cache_scope,
                batch_id=effective_batch_id,
                retry_429_max=retry_429_max,
                retry_429_backoff_ms=retry_429_backoff_ms,
            )
        )

    _write_checkpoint(checkpoint_path, checkpoint)
    _write_summary_files(checkpoint, output_dir_abs)

    if run_tasks:
        _execute_batch_tasks(
            tasks=run_tasks,
            checkpoint=checkpoint,
            items=items,
            checkpoint_path=checkpoint_path,
            output_dir=output_dir_abs,
            reusable_by_hash=reusable_by_hash,
            workers=resolved_workers,
            prefetch=resolved_prefetch,
            limiter_mode=resolved_rate_limit_mode,
            limiter_init=min(resolved_rate_limit_init, resolved_workers),
            limiter_max=min(resolved_rate_limit_max, resolved_workers),
        )

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

    if excel:
        if excel_output is None:
            resolved_excel_output = output_dir_abs / _BATCH_EXCEL_FILE
        else:
            resolved_excel_output = excel_output.resolve()
        try:
            exported = _generate_batch_excel(
                summary,
                output_dir_abs / _SUMMARY_JSON_FILE,
                resolved_excel_output,
            )
            typer.echo(f"已写入: {resolved_excel_output} (rows={exported})")
        except Exception as exc:  # pragma: no cover - defensive
            typer.echo(f"Warning: Excel 汇总生成失败: {exc}")

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


@app.command("excel", help="根据批量 summary 生成 Excel 汇总（XLSX）")
def excel_batch(
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
        help="输出 Excel 路径（默认: <batch-output-dir>/batch_summary.xlsx）",
    ),
) -> None:
    summary_path, _ = _resolve_summary_input(source.resolve())
    summary = _load_summary_or_raise(summary_path)
    default_output = _default_excel_output(summary_path)
    output_path = output.resolve() if output is not None else default_output
    exported = _generate_batch_excel(summary, summary_path, output_path)
    typer.echo(f"已写入: {output_path} (rows={exported})")


def _execute_batch_tasks(
    *,
    tasks: deque[_BatchTask],
    checkpoint: dict[str, Any],
    items: dict[str, dict[str, Any]],
    checkpoint_path: Path,
    output_dir: Path,
    reusable_by_hash: dict[str, Path],
    workers: int,
    prefetch: int,
    limiter_mode: Literal["adaptive", "fixed"],
    limiter_init: int,
    limiter_max: int,
) -> None:
    limiter = _AdaptiveConcurrencyController(
        mode=limiter_mode,
        current_limit=max(1, limiter_init),
        min_limit=1,
        max_limit=max(1, limiter_max),
        success_window=_ADAPTIVE_SUCCESS_WINDOW,
    )

    if workers <= 1:
        while tasks:
            task = tasks.popleft()
            _mark_task_running(
                task=task,
                items=items,
                checkpoint=checkpoint,
                checkpoint_path=checkpoint_path,
                output_dir=output_dir,
            )
            typer.echo(f"[{task.index}/{task.total}] run {task.relative_path}")
            task_result = _run_batch_item_task(task)
            _apply_task_result(
                task_result=task_result,
                checkpoint=checkpoint,
                items=items,
                checkpoint_path=checkpoint_path,
                output_dir=output_dir,
                reusable_by_hash=reusable_by_hash,
            )
            limiter.observe(
                success=task_result.get("status") == "success",
                had_retryable_error=bool(task_result.get("had_retryable_error")),
            )
        return

    inflight_cap = max(1, prefetch)
    futures: dict[Future[dict[str, Any]], _BatchTask] = {}
    with _PROCESS_POOL_EXECUTOR(max_workers=workers) as executor:
        while tasks or futures:
            allowed = max(1, min(limiter.current_limit, inflight_cap))
            while tasks and len(futures) < allowed:
                task = tasks.popleft()
                _mark_task_running(
                    task=task,
                    items=items,
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                    output_dir=output_dir,
                )
                typer.echo(f"[{task.index}/{task.total}] run {task.relative_path}")
                future = executor.submit(_run_batch_item_task, task)
                futures[future] = task

            if not futures:
                continue

            done, _ = wait(set(futures), return_when=FIRST_COMPLETED)
            for future in done:
                task = futures.pop(future)
                try:
                    task_result = future.result()
                except Exception as exc:  # pragma: no cover - defensive
                    task_result = _task_failure_payload(task, exc)

                _apply_task_result(
                    task_result=task_result,
                    checkpoint=checkpoint,
                    items=items,
                    checkpoint_path=checkpoint_path,
                    output_dir=output_dir,
                    reusable_by_hash=reusable_by_hash,
                )

                before = limiter.current_limit
                limiter.observe(
                    success=task_result.get("status") == "success",
                    had_retryable_error=bool(task_result.get("had_retryable_error")),
                )
                after = limiter.current_limit
                if after != before:
                    typer.echo(f"[rate-limit] 并发额度调整: {before} -> {after}")


def _mark_task_running(
    *,
    task: _BatchTask,
    items: dict[str, dict[str, Any]],
    checkpoint: dict[str, Any],
    checkpoint_path: Path,
    output_dir: Path,
) -> None:
    item = items[task.relative_path]
    item["status"] = "running"
    item["error"] = None
    item["updated_at"] = _now_iso()
    _write_checkpoint(checkpoint_path, checkpoint)
    _write_summary_files(checkpoint, output_dir)


def _run_batch_item_task(task: _BatchTask) -> dict[str, Any]:
    subdir = Path(task.batch_output_dir) / task.output_subdir
    retry_count = 0
    retryable_errors = 0
    had_retryable_error = False

    for attempt in range(task.retry_429_max + 1):
        try:
            result = run_rob2(
                Rob2Input(pdf_path=task.pdf_path),
                task.options_payload,
                persist_enabled=task.persist_enabled,
                persistence_dir=task.persistence_dir,
                persistence_scope=task.persistence_scope,
                cache_dir=task.cache_dir,
                cache_scope=task.cache_scope,
                batch_id=task.batch_id,
            )
            write_run_output_dir(
                result,
                subdir,
                include_table=task.include_table,
                html=task.html,
                docx=task.docx,
                pdf=task.pdf,
                pdf_name=task.pdf_name,
            )
            _write_batch_item_meta(
                output_dir=subdir,
                pdf_sha256=task.pdf_sha256,
                relative_path=task.relative_path,
            )
            domain_risks = {
                str(domain.domain): domain.risk for domain in result.result.domains
            }
            return {
                "index": task.index,
                "total": task.total,
                "relative_path": task.relative_path,
                "status": "success",
                "run_id": result.run_id,
                "runtime_ms": result.runtime_ms,
                "overall_risk": result.result.overall.risk,
                "domain_risks": domain_risks,
                "error": None,
                "pdf_sha256": task.pdf_sha256,
                "result_dir": str(subdir),
                "retry_count": retry_count,
                "retryable_errors": retryable_errors,
                "had_retryable_error": had_retryable_error,
            }
        except Exception as exc:  # pragma: no cover - exercised via integration tests
            error_text = _format_error(exc)
            retryable = _is_retryable_error(error_text)
            if retryable:
                had_retryable_error = True
                retryable_errors += 1

            if retryable and attempt < task.retry_429_max:
                retry_count += 1
                backoff_seconds = (task.retry_429_backoff_ms / 1000.0) * (2**attempt)
                sleep(max(0.0, backoff_seconds))
                continue

            return {
                "index": task.index,
                "total": task.total,
                "relative_path": task.relative_path,
                "status": "failed",
                "run_id": None,
                "runtime_ms": None,
                "overall_risk": None,
                "domain_risks": {},
                "error": error_text,
                "pdf_sha256": task.pdf_sha256,
                "result_dir": str(subdir),
                "retry_count": retry_count,
                "retryable_errors": retryable_errors,
                "had_retryable_error": had_retryable_error,
            }

    return _task_failure_payload(task, RuntimeError("unexpected retry loop exhaustion"))


def _task_failure_payload(task: _BatchTask, exc: Exception) -> dict[str, Any]:
    error_text = _format_error(exc)
    return {
        "index": task.index,
        "total": task.total,
        "relative_path": task.relative_path,
        "status": "failed",
        "run_id": None,
        "runtime_ms": None,
        "overall_risk": None,
        "domain_risks": {},
        "error": error_text,
        "pdf_sha256": task.pdf_sha256,
        "result_dir": str(Path(task.batch_output_dir) / task.output_subdir),
        "retry_count": 0,
        "retryable_errors": 1 if _is_retryable_error(error_text) else 0,
        "had_retryable_error": _is_retryable_error(error_text),
    }


def _apply_task_result(
    *,
    task_result: dict[str, Any],
    checkpoint: dict[str, Any],
    items: dict[str, dict[str, Any]],
    checkpoint_path: Path,
    output_dir: Path,
    reusable_by_hash: dict[str, Path],
) -> None:
    rel_path = str(task_result["relative_path"])
    item = items[rel_path]
    status = str(task_result.get("status") or "failed")

    if status == "success":
        item["status"] = "success"
        item["run_id"] = task_result.get("run_id")
        item["runtime_ms"] = task_result.get("runtime_ms")
        item["overall_risk"] = task_result.get("overall_risk")
        item["domain_risks"] = task_result.get("domain_risks") or {}
        item["error"] = None
        pdf_sha256 = task_result.get("pdf_sha256")
        result_dir = task_result.get("result_dir")
        if isinstance(pdf_sha256, str) and isinstance(result_dir, str):
            reusable_by_hash[pdf_sha256] = Path(result_dir).resolve()
        typer.echo(
            f"[{task_result['index']}/{task_result['total']}] done {rel_path}"
        )
    else:
        item["status"] = "failed"
        item["run_id"] = None
        item["runtime_ms"] = None
        item["overall_risk"] = None
        item["domain_risks"] = {}
        item["error"] = str(task_result.get("error") or "unknown error")
        typer.echo(
            f"[{task_result['index']}/{task_result['total']}] failed {rel_path}: {item['error']}"
        )

    item["updated_at"] = _now_iso()
    _increment_runtime_meta(
        checkpoint,
        completed=1,
        retryable_errors=int(task_result.get("retryable_errors") or 0),
    )
    _write_checkpoint(checkpoint_path, checkpoint)
    _write_summary_files(checkpoint, output_dir)


def _ensure_runtime_meta(
    checkpoint: dict[str, Any],
    *,
    workers: int,
    max_inflight_llm: int,
    rate_limit_mode: str,
) -> None:
    meta = checkpoint.get("runtime_meta")
    if not isinstance(meta, dict):
        meta = {}
        checkpoint["runtime_meta"] = meta
    meta.setdefault("started_at", _now_iso())
    meta["workers"] = workers
    meta["max_inflight_llm"] = max_inflight_llm
    meta["rate_limit_mode"] = rate_limit_mode
    meta.setdefault("completed_items", 0)
    meta.setdefault("retryable_error_count", 0)


def _increment_runtime_meta(
    checkpoint: dict[str, Any],
    *,
    completed: int = 0,
    retryable_errors: int = 0,
) -> None:
    meta = checkpoint.get("runtime_meta")
    if not isinstance(meta, dict):
        return
    meta["completed_items"] = int(meta.get("completed_items") or 0) + int(completed)
    meta["retryable_error_count"] = int(meta.get("retryable_error_count") or 0) + int(
        retryable_errors
    )


def _resolve_workers(cli_value: int | None, config_value: int | None) -> int:
    if cli_value is not None:
        return max(1, int(cli_value))
    if config_value is not None:
        return max(1, int(config_value))
    cpu = os.cpu_count() or 1
    return max(1, min(4, cpu))


def _resolve_int_with_default(
    cli_value: int | None,
    config_value: int | None,
    *,
    fallback: int,
) -> int:
    if cli_value is not None:
        return int(cli_value)
    if config_value is not None:
        return int(config_value)
    return int(fallback)


def _resolve_rate_limit_mode(
    cli_value: str | None,
    config_value: str | None,
) -> Literal["adaptive", "fixed"]:
    raw = (cli_value or config_value or "adaptive").strip().lower()
    if raw not in {"adaptive", "fixed"}:
        raise typer.BadParameter("--rate-limit-mode 仅支持 adaptive|fixed")
    return "adaptive" if raw == "adaptive" else "fixed"


def _is_retryable_error(error_text: str) -> bool:
    normalized = error_text.strip().lower()
    if not normalized:
        return False
    return any(token in normalized for token in _RETRYABLE_ERROR_HINTS)


def _build_initial_checkpoint(
    *,
    input_dir_abs: str,
    output_dir_abs: str,
    options_hash: str,
    file_list_hash: str,
    batch_id: str | None,
    batch_name: str | None,
    file_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    items = []
    for entry in file_entries:
        rel_path = str(entry["relative_path"])
        pdf_sha256 = str(entry["pdf_sha256"])
        output_subdir = str(Path(rel_path).with_suffix(""))
        items.append(
            {
                "relative_path": rel_path,
                "pdf_sha256": pdf_sha256,
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
    if data.get("version") != _CHECKPOINT_VERSION:
        raise typer.BadParameter(
            f"checkpoint 版本不兼容: {path}。请使用 --reset 重新执行。"
        )
    if not isinstance(data.get("items"), list):
        raise typer.BadParameter(f"checkpoint items 缺失: {path}")
    for raw_item in data["items"]:
        if not isinstance(raw_item, dict):
            raise typer.BadParameter(f"checkpoint item 格式错误: {path}")
        pdf_sha256 = raw_item.get("pdf_sha256")
        if not isinstance(pdf_sha256, str) or not pdf_sha256.strip():
            raise typer.BadParameter(
                f"checkpoint 缺少 pdf_sha256: {path}。请使用 --reset 重新执行。"
            )
    return data


def _assert_checkpoint_compatible(
    checkpoint: dict[str, Any],
    *,
    input_dir_abs: str,
    output_dir_abs: str,
    file_list_hash: str,
    batch_id: str | None,
    batch_name: str | None,
) -> None:
    errors: list[str] = []
    if checkpoint.get("input_dir_abs") != input_dir_abs:
        errors.append("input_dir_abs")
    if checkpoint.get("output_dir_abs") != output_dir_abs:
        errors.append("output_dir_abs")
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


def _build_file_entries(input_dir: Path, pdf_files: list[Path]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in pdf_files:
        entries.append(
            {
                "relative_path": path.relative_to(input_dir).as_posix(),
                "pdf_path": path,
                "pdf_sha256": sha256_file(path),
            }
        )
    return entries


def _build_file_list_hash(entries: list[dict[str, Any]]) -> str:
    signature = [
        {
            "relative_path": str(entry["relative_path"]),
            "pdf_sha256": str(entry["pdf_sha256"]),
        }
        for entry in entries
    ]
    return hash_payload(signature)


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


def _build_reusable_result_index(output_dir: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    for meta_path in sorted(output_dir.rglob(_BATCH_ITEM_META_FILE)):
        meta = _load_batch_item_meta(meta_path)
        if meta is None:
            continue
        pdf_sha256 = meta.get("pdf_sha256")
        if not isinstance(pdf_sha256, str) or not pdf_sha256.strip():
            continue
        result_dir = meta_path.parent.resolve()
        if not (result_dir / "result.json").exists():
            continue
        index[pdf_sha256] = result_dir
    return index


def _load_batch_item_meta(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _write_batch_item_meta(
    *,
    output_dir: Path,
    pdf_sha256: str,
    relative_path: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _BATCH_ITEM_META_VERSION,
        "pdf_sha256": pdf_sha256,
        "relative_path": relative_path,
        "updated_at": _now_iso(),
    }
    (output_dir / _BATCH_ITEM_META_FILE).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _materialize_reused_output(*, source_dir: Path, target_dir: Path) -> None:
    source = source_dir.resolve()
    target = target_dir.resolve()
    if source == target:
        return

    target.mkdir(parents=True, exist_ok=True)
    for name in _MANAGED_RESULT_FILES:
        source_path = source / name
        target_path = target / name
        if source_path.exists() and source_path.is_file():
            _copy_or_link_file(source_path, target_path)
            continue
        if target_path.exists():
            if target_path.is_file() or target_path.is_symlink():
                target_path.unlink()
            else:
                shutil.rmtree(target_path)


def _copy_or_link_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.is_file() or target.is_symlink():
            target.unlink()
        else:
            shutil.rmtree(target)
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _read_result_summary(result_path: Path) -> dict[str, Any] | None:
    if not result_path.exists():
        return None
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None

    result_obj = payload.get("result")
    if not isinstance(result_obj, dict):
        return None
    overall = result_obj.get("overall")
    if not isinstance(overall, dict):
        return None
    overall_risk = overall.get("risk")
    if not isinstance(overall_risk, str) or not overall_risk.strip():
        return None

    run_id = payload.get("run_id")
    runtime_ms = payload.get("runtime_ms")
    domains = result_obj.get("domains")
    if not isinstance(domains, list):
        domains = []

    domain_risks: dict[str, str] = {}
    for domain in domains:
        if not isinstance(domain, dict):
            continue
        domain_id = domain.get("domain")
        domain_risk = domain.get("risk")
        if isinstance(domain_id, str) and isinstance(domain_risk, str):
            domain_risks[domain_id] = domain_risk

    return {
        "run_id": run_id if isinstance(run_id, str) else None,
        "runtime_ms": runtime_ms if isinstance(runtime_ms, int) else None,
        "overall_risk": overall_risk,
        "domain_risks": domain_risks,
    }


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
    summary = {
        "version": checkpoint.get("version"),
        "input_dir_abs": checkpoint.get("input_dir_abs"),
        "output_dir_abs": checkpoint.get("output_dir_abs"),
        "batch_id": checkpoint.get("batch_id"),
        "batch_name": checkpoint.get("batch_name"),
        "counts": counts,
        "items": sorted(items, key=lambda item: str(item.get("relative_path") or "")),
    }

    runtime_meta = checkpoint.get("runtime_meta")
    if isinstance(runtime_meta, dict):
        metrics = dict(runtime_meta)
        runtime_values = sorted(
            int(item["runtime_ms"])
            for item in items
            if isinstance(item.get("runtime_ms"), int)
        )
        if runtime_values:
            metrics["avg_runtime_ms"] = int(sum(runtime_values) / len(runtime_values))
            metrics["p95_runtime_ms"] = runtime_values[min(len(runtime_values) - 1, int(len(runtime_values) * 0.95))]

        started_at = metrics.get("started_at")
        completed_items = int(metrics.get("completed_items") or 0)
        if isinstance(started_at, str):
            try:
                elapsed_seconds = max(
                    1.0,
                    (datetime.now(timezone.utc) - datetime.fromisoformat(started_at)).total_seconds(),
                )
                metrics["throughput_docs_per_hour"] = round(
                    (completed_items / elapsed_seconds) * 3600.0,
                    2,
                )
            except ValueError:
                pass
        summary["runtime_meta"] = metrics

    return summary


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


def _default_excel_output(summary_path: Path) -> Path:
    return summary_path.parent / _BATCH_EXCEL_FILE


def _generate_batch_excel(
    summary: dict[str, Any],
    summary_path: Path,
    output_path: Path,
) -> int:
    try:
        return generate_batch_summary_excel(
            summary,
            summary_path=summary_path,
            output_path=output_path,
        )
    except ValueError as exc:
        raise typer.BadParameter(f"Excel 汇总生成失败: {exc}") from exc


def _format_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["app"]
