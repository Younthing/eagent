"""Factories and helpers for wiring the Typer CLI application."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from eagent import __version__

from .commands import register_cli_commands


def create_cli_app(console: Optional[Console] = None) -> typer.Typer:
    """Build and configure the Typer CLI application."""

    cli_console = console or Console()
    app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})

    def version_callback(value: bool) -> None:
        if not value:
            return

        cli_console.print(f"eagent {__version__}")
        raise typer.Exit()

    @app.callback()
    def main(
        ctx: typer.Context,
        version: bool = typer.Option(
            None,
            "--version",
            "-v",
            help="Show the installed version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ) -> None:
        return

    register_cli_commands(app, console=cli_console)
    return app


def run_cli(console: Optional[Console] = None) -> None:
    """Execute the CLI application."""

    create_cli_app(console=console)()
