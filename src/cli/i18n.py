"""CLI localization for Chinese help output."""

from __future__ import annotations

import click
import typer.rich_utils as rich_utils
from typer.core import TyperCommand, TyperGroup


_USAGE_PREFIX = "用法: "
_HELP_TEXT = "显示帮助并退出"


def apply_cli_localization() -> None:
    _patch_rich_labels()
    _patch_usage_labels()
    _patch_help_option()
    _patch_click_errors()


def _patch_rich_labels() -> None:
    rich_utils.ARGUMENTS_PANEL_TITLE = "参数"
    rich_utils.OPTIONS_PANEL_TITLE = "选项"
    rich_utils.COMMANDS_PANEL_TITLE = "命令"
    rich_utils.ERRORS_PANEL_TITLE = "错误"
    rich_utils.ABORTED_TEXT = "已中止"
    rich_utils.DEFAULT_STRING = "[默认: {}]"
    rich_utils.ENVVAR_STRING = "[环境变量: {}]"
    rich_utils.REQUIRED_LONG_STRING = "[必填]"
    rich_utils.RICH_HELP = "使用 [blue]'{command_path} {help_option}'[/] 查看帮助"

    rich_utils.OptionHighlighter.highlights = [
        r"(^|\W)(?P<switch>\-\w+)(?![a-zA-Z0-9])",
        r"(^|\W)(?P<option>\-\-[\w\-]+)(?![a-zA-Z0-9])",
        r"(?P<metavar>\<[^\>]+\>)",
        r"(?P<usage>用法: )",
    ]
    rich_utils.highlighter = rich_utils.OptionHighlighter()


def _patch_usage_labels() -> None:
    def _format_usage(self: click.Command, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        pieces = [
            piece.replace("[OPTIONS]", "[选项]") for piece in self.collect_usage_pieces(ctx)
        ]
        formatter.write_usage(ctx.command_path, " ".join(pieces), prefix=_USAGE_PREFIX)

    TyperCommand.format_usage = _format_usage  # type: ignore[assignment]
    TyperGroup.format_usage = _format_usage  # type: ignore[assignment]


def _patch_help_option() -> None:
    def _get_help_option(self: click.Command, ctx: click.Context) -> click.Option | None:
        option = click.core.Command.get_help_option(self, ctx)
        if option is not None:
            option.help = _HELP_TEXT
        return option

    TyperCommand.get_help_option = _get_help_option  # type: ignore[assignment]
    TyperGroup.get_help_option = _get_help_option  # type: ignore[assignment]


def _patch_click_errors() -> None:
    import click.exceptions as exceptions

    translations = {
        "Missing argument": "缺少参数",
        "Missing option": "缺少选项",
        "Missing parameter": "缺少参数",
        "Missing {param_type}": "缺少{param_type}",
    }

    def _translate(text: str) -> str:
        return translations.get(text, text)

    exceptions._ = _translate  # type: ignore[attr-defined]


__all__ = ["apply_cli_localization"]
