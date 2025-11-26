from dotenv import load_dotenv
import typer
from rich.console import Console

from eagent import __version__
from eagent.cli import register_cli_commands

load_dotenv()

app = typer.Typer(context_settings={"help_option_names": ["-h", "--help"]})
console = Console()


def version_callback(value: bool):
    if not value:
        return
    console.print(f"eagent {__version__}")
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
):
    return


register_cli_commands(app, console=console)


if __name__ == "__main__":
    app()
