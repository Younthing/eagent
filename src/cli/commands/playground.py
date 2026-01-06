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
        from playground.domain_playground import main_d1
    except ModuleNotFoundError as exc:
        raise typer.BadParameter(
            "D1 调试台依赖可视化组件，请安装可选依赖：uv pip install -e '.[visual]'"
        ) from exc
    main_d1()


@app.command("d2", help="启动 D2 调试台")
def d2_playground() -> None:
    """启动 D2 调试台"""
    try:
        from playground.domain_playground import main_d2
    except ModuleNotFoundError as exc:
        raise typer.BadParameter(
            "D2 调试台依赖可视化组件，请安装可选依赖：uv pip install -e '.[visual]'"
        ) from exc
    main_d2()


@app.command("d3", help="启动 D3 调试台")
def d3_playground() -> None:
    """启动 D3 调试台"""
    try:
        from playground.domain_playground import main_d3
    except ModuleNotFoundError as exc:
        raise typer.BadParameter(
            "D3 调试台依赖可视化组件，请安装可选依赖：uv pip install -e '.[visual]'"
        ) from exc
    main_d3()


@app.command("d4", help="启动 D4 调试台")
def d4_playground() -> None:
    """启动 D4 调试台"""
    try:
        from playground.domain_playground import main_d4
    except ModuleNotFoundError as exc:
        raise typer.BadParameter(
            "D4 调试台依赖可视化组件，请安装可选依赖：uv pip install -e '.[visual]'"
        ) from exc
    main_d4()


@app.command("d5", help="启动 D5 调试台")
def d5_playground() -> None:
    """启动 D5 调试台"""
    try:
        from playground.domain_playground import main_d5
    except ModuleNotFoundError as exc:
        raise typer.BadParameter(
            "D5 调试台依赖可视化组件，请安装可选依赖：uv pip install -e '.[visual]'"
        ) from exc
    main_d5()


__all__ = ["app"]
