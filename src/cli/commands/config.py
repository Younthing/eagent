"""Configuration inspection commands."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from core.config import Settings, get_settings
from .shared import emit_json


app = typer.Typer(
    help="配置查看与导出",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


@app.command("show", help="查看当前生效配置")
def show_config(
    json_out: bool = typer.Option(True, "--json/--no-json", help="输出 JSON"),
) -> None:
    settings = get_settings()
    payload = settings.model_dump()
    if json_out:
        emit_json(payload)
        return
    for key, value in payload.items():
        typer.echo(f"{key}={value}")


@app.command("export", help="导出配置为 JSON")
def export_config(
    output: Path | None = typer.Option(
        None,
        "--output",
        help="导出的 JSON 文件路径（默认输出到 stdout）",
    ),
) -> None:
    payload = get_settings().model_dump()
    if output is None:
        emit_json(payload)
        return
    output.write_text(json_dumps(payload), encoding="utf-8")
    typer.echo(f"已写入: {output}")


@app.command("diff", help="显示与默认值的差异")
def diff_config() -> None:
    settings = get_settings()
    defaults = _settings_defaults()
    current = settings.model_dump()
    diff: dict[str, dict[str, Any]] = {}
    for key, value in current.items():
        default = defaults.get(key)
        if value != default:
            diff[key] = {"value": value, "default": default}
    emit_json(diff)


def _settings_defaults() -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    for name, field in Settings.model_fields.items():
        defaults[name] = field.default
    return defaults


def json_dumps(payload: object) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2)


__all__ = ["app"]
