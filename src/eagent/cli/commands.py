"""Typer command definitions for the CLI entrypoint."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import typer
from rich.console import Console
from rich.prompt import Prompt

from eagent.runner import AnalysisSession
from eagent.state import Task
from eagent.utils.parsing import parse_pdf_structure

Plan = List[Task]


def register_cli_commands(
    app: typer.Typer,
    *,
    console: Optional[Console] = None,
) -> None:
    """Attach CLI commands to the provided Typer application."""

    cli_console = console or Console()

    def show_plan(tasks: Sequence[Task]) -> None:
        if not tasks:
            cli_console.print("[yellow]暂无可展示的分析计划。[/yellow]")
            return

        cli_console.print("\n[yellow]=== AI 提议的分析计划 ===[/yellow]")
        for idx, task in enumerate(tasks, start=1):
            cli_console.print(
                f"{idx}. 维度: [bold]{task.dimension}[/bold] -> "
                f"读取章节: [cyan]{task.section_filter}[/cyan]"
            )

    def review_plan(session: AnalysisSession, initial_plan: Plan) -> Tuple[bool, Plan]:
        current_plan = list(initial_plan)

        while True:
            action = Prompt.ask(
                "\n下一步操作?", choices=["continue", "add", "quit"], default="continue"
            )
            if action == "quit":
                cli_console.print("[yellow]已取消运行。[/yellow]")
                return False, current_plan

            if action == "continue":
                return True, current_plan

            new_dim = Prompt.ask("输入新维度名称")
            new_key = Prompt.ask("输入读取章节Key", default="methods")
            new_task = Task(
                dimension=new_dim,
                section_filter=new_key,
                search_query=new_dim,
            )

            current_plan = current_plan + [new_task]
            session.update_plan(current_plan)
            cli_console.print("[green]计划已更新。[/green]")
            show_plan(session.plan)
            current_plan = session.plan

    @app.command(help="带 HITL 的文献分析流程。")
    def analyze(
        file_path: str = typer.Argument(..., help="待分析文档路径。"),
    ) -> None:
        doc_structure = parse_pdf_structure(file_path)
        session = AnalysisSession(doc_structure)

        cli_console.print("[bold blue]🤖 AI 正在规划分析任务...[/bold blue]")
        plan = session.generate_plan()
        if not plan:
            cli_console.print("[red]Graph failed to produce a plan.[/red]")
            return

        show_plan(plan)
        should_continue, _ = review_plan(session, plan)
        if not should_continue:
            return

        cli_console.print("🚀 并行分析中...")
        final_report = session.run()
        if not final_report:
            cli_console.print("[red]分析未产生报告。[/red]")
            return

        cli_console.print("\n[bold green]=== 最终报告 ===[/bold green]")
        cli_console.print(final_report)
