import typer
from rich.console import Console
from rich.prompt import Prompt

from eagent.graph import build_graph
from eagent.state import Task
from eagent.utils.parsing import parse_pdf_structure

app = typer.Typer()
console = Console()


@app.command()
def analyze(file_path: str):
    """带 HITL 的文献分析流程。"""
    doc_structure = parse_pdf_structure(file_path)

    app_graph = build_graph()
    thread_config = {"configurable": {"thread_id": "session_user_1"}}

    initial_state = {"doc_structure": doc_structure, "plan": [], "analyses": []}

    console.print("[bold blue]🤖 AI 正在规划分析任务...[/bold blue]")

    for _ in app_graph.stream(initial_state, thread_config):
        pass

    snapshot = app_graph.get_state(thread_config)
    if not snapshot.values:
        console.print("[red]Graph failed to start.[/red]")
        return

    current_plan = snapshot.values["plan"]

    console.print("\n[yellow]=== AI 提议的分析计划 ===[/yellow]")
    for i, task in enumerate(current_plan):
        console.print(
            f"{i+1}. 维度: [bold]{task.dimension}[/bold] -> 读取章节: [cyan]{task.section_filter}[/cyan]"
        )

    user_action = Prompt.ask("\n下一步操作?", choices=["continue", "add", "quit"], default="continue")

    if user_action == "quit":
        return
    elif user_action == "add":
        new_dim = Prompt.ask("输入新维度名称")
        new_key = Prompt.ask("输入读取章节Key", default="methods")
        new_task = Task(dimension=new_dim, section_filter=new_key, search_query=new_dim)
        updated_plan = current_plan + [new_task]
        app_graph.update_state(thread_config, {"plan": updated_plan})
        console.print("[green]计划已更新，继续执行...[/green]")

    console.print("🚀 并行分析中...")
    final_output = None
    for event in app_graph.stream(None, thread_config):
        if "summarizer" in event:
            final_output = event["summarizer"]

    if final_output:
        console.print("\n[bold green]=== 最终报告 ===[/bold green]")
        console.print(final_output["final_report"])


if __name__ == "__main__":
    app()
