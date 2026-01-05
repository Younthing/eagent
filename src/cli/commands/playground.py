"""Playground commands (interactive tools)."""

from __future__ import annotations

import typer


app = typer.Typer(
    help="交互式调试工具",
    context_settings={"help_option_names": ["-h", "--help"]},
    add_completion=False,
    no_args_is_help=True,
    options_metavar="[选项]",
    subcommand_metavar="命令 [参数]",
)


@app.command("d1", help="启动 D1 调试台")
def d1_playground() -> None:
    """启动 D1 调试台"""
    try:
        from playground.d1_playground import main
    except ModuleNotFoundError as exc:
        raise typer.BadParameter(
            "D1 调试台依赖可视化组件，请安装可选依赖：uv pip install -e '.[visual]'"
        ) from exc
    main()


__all__ = ["app"]
