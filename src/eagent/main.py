import typer
from rich.console import Console
from rich.prompt import Prompt

from eagent import __version__
from eagent.runner import AnalysisSession
from eagent.state import Task
from eagent.utils.parsing import parse_pdf_structure

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


@app.command()
def analyze(file_path: str):
    """带 HITL 的文献分析流程。"""
    doc_structure = parse_pdf_structure(file_path)
    session = AnalysisSession(doc_structure)

    console.print("[bold blue]🤖 AI 正在规划分析任务...[/bold blue]")
    plan = session.generate_plan()
    if not plan:
        console.print("[red]Graph failed to produce a plan.[/red]")
        return

    def show_plan(tasks: list[Task]) -> None:
        console.print("\n[yellow]=== AI 提议的分析计划 ===[/yellow]")
        for i, task in enumerate(tasks):
            console.print(
                f"{i+1}. 维度: [bold]{task.dimension}[/bold] -> 读取章节: [cyan]{task.section_filter}[/cyan]"
            )

    show_plan(plan)

    while True:
        action = Prompt.ask(
            "\n下一步操作?", choices=["continue", "add", "quit"], default="continue"
        )
        if action == "quit":
            console.print("[yellow]已取消运行。[/yellow]")
            return
        if action == "continue":
            break

        new_dim = Prompt.ask("输入新维度名称")
        new_key = Prompt.ask("输入读取章节Key", default="methods")
        new_task = Task(dimension=new_dim, section_filter=new_key, search_query=new_dim)
        updated_plan = plan + [new_task]
        session.update_plan(updated_plan)
        plan = session.plan
        console.print("[green]计划已更新。[/green]")
        show_plan(plan)

    console.print("🚀 并行分析中...")
    final_report = session.run()
    if not final_report:
        console.print("[red]分析未产生报告。[/red]")
        return

    console.print("\n[bold green]=== 最终报告 ===[/bold green]")
    console.print(final_report)


if __name__ == "__main__":
    app()
