# Literature Agent (Upgraded)

并行 Map-Reduce 文献分析智能体示例，集成 LangChain Hub 提示词、LangSmith 追踪、上下文切片、节点级重试与 HITL 控制。

---

## 1. 目录结构

```text
eagent/
├── .env.example                # 环境变量模版
├── pyproject.toml
├── main.py                     # CLI + HITL
├── src/
│   └── eagent/
│       ├── __init__.py
│       ├── state.py            # 数据结构
│       ├── prompts.py          # Hub 拉取 + 本地兜底
│       ├── graph.py            # 编排 (含 interrupt_before)
│       ├── utils/
│       │   └── parsing.py      # @traceable 文档解析
│       └── nodes/
│           ├── planner.py      # 规划 + Context Slicing
│           ├── worker.py       # 重试 + 校验
│           └── aggregator.py   # 汇总
└── tests/
    └── eval.py                 # LangSmith KV 评估
```

---

## 2. 状态与模型 (`src/eagent/state.py`)

```python
import operator
from typing import Annotated, Dict, List
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

class Task(BaseModel):
    dimension: str
    section_filter: str
    search_query: str

class AnalysisResult(BaseModel):
    dimension: str
    content: str
    is_valid: bool = Field(default=True)
    retry_count: int = Field(default=0)

class AgentState(TypedDict):
    doc_structure: Dict[str, str]
    plan: List[Task]
    analyses: Annotated[List[AnalysisResult], operator.add]
    final_report: str
```

---

## 3. Prompt Hub (`src/eagent/prompts.py`)

```python
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate

_DEFAULT_PLANNER = ChatPromptTemplate.from_template(
    "分析文档结构: {doc_keys}。\n"
    "请生成分析计划。对于每个维度，务必指定最相关的 'section_filter' (章节Key)。"
)

_DEFAULT_WORKER = ChatPromptTemplate.from_template(
    "你负责分析 {dimension}。\n"
    "请仅基于以下提供的片段进行分析，不要编造。\n"
    "片段内容:\n{context}"
)

def get_prompt(repo_id: str, default: ChatPromptTemplate) -> ChatPromptTemplate:
    try:
        return hub.pull(repo_id)
    except Exception as exc:
        print(f"⚠️ Warning: Failed to pull prompt {repo_id}, using default. Error: {exc}")
        return default

planner_prompt = get_prompt("my-org/paper-analysis-planner", _DEFAULT_PLANNER)
worker_prompt = get_prompt("my-org/paper-section-analyzer", _DEFAULT_WORKER)
```

---

## 4. Traceable 解析 (`src/eagent/utils/parsing.py`)

```python
from typing import Dict
from langsmith import traceable

@traceable(run_type="parser", name="PDF Structure Parser")
def parse_pdf_structure(file_path: str) -> Dict[str, str]:
    return {
        "abstract": "This paper proposes a new Transformer architecture...",
        "methods": "We utilized a 12-layer attention mechanism with...",
        "results": "Our model achieved 98.5% accuracy on the test set...",
        "conclusion": "Future work includes...",
    }
```

---

## 5. 节点实现

### 5.1 Planner (`src/eagent/nodes/planner.py`)

```python
from typing import List
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
from eagent.prompts import planner_prompt
from eagent.state import AgentState, Task

llm = ChatOpenAI(model="gpt-4o", temperature=0)

class PlanningOutput(BaseModel):
    tasks: List[Task]

def plan_node(state: AgentState):
    doc_keys = list(state["doc_structure"].keys())
    chain = planner_prompt | llm.with_structured_output(PlanningOutput)
    result: PlanningOutput = chain.invoke({"doc_keys": str(doc_keys)})
    return {"plan": result.tasks}
```

### 5.2 Worker (`src/eagent/nodes/worker.py`)

```python
from langchain_openai import ChatOpenAI
from eagent.prompts import worker_prompt
from eagent.state import AnalysisResult, Task

llm = ChatOpenAI(model="gpt-4o", temperature=0)

def extract_context(doc: dict, task: Task) -> str:
    content = doc.get(task.section_filter)
    if not content:
        return str(doc)[:2000]
    return content

def worker_node(state: dict):
    task: Task = state["task"]
    doc = state["doc_structure"]
    context = extract_context(doc, task)

    max_retries = 3
    current_try = 0
    last_error = None

    while current_try < max_retries:
        try:
            chain = worker_prompt | llm.with_structured_output(AnalysisResult)
            result: AnalysisResult = chain.invoke(
                {"dimension": task.dimension, "context": context}
            )
            if len(result.content) < 10:
                raise ValueError("Content too short, looks like hallucination.")
            result.retry_count = current_try
            return {"analyses": [result]}
        except Exception as exc:
            current_try += 1
            last_error = exc
            print(f"Node retry {current_try}/{max_retries} for {task.dimension}: {exc}")

    return {
        "analyses": [
            AnalysisResult(
                dimension=task.dimension,
                content=f"Analysis Failed after retries. Error: {last_error}",
                is_valid=False,
                retry_count=current_try,
            )
        ]
    }
```

### 5.3 Aggregator (`src/eagent/nodes/aggregator.py`)

```python
from eagent.state import AgentState

def aggregator_node(state: AgentState):
    texts = [
        f"## {a.dimension}\n{a.content}"
        for a in state.get("analyses", [])
        if a.is_valid
    ]
    return {"final_report": "\n\n".join(texts)}
```

---

## 6. 图编排 (`src/eagent/graph.py`)

```python
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import Send, START, END
from langgraph.graph import StateGraph

from eagent.nodes.aggregator import aggregator_node
from eagent.nodes.planner import plan_node
from eagent.nodes.worker import worker_node
from eagent.state import AgentState

def map_analyses(state: AgentState):
    return [
        Send("analyzer", {"task": task, "doc_structure": state["doc_structure"]})
        for task in state["plan"]
    ]

def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("planner", plan_node)
    workflow.add_node("analyzer", worker_node)
    workflow.add_node("summarizer", aggregator_node)
    workflow.add_edge(START, "planner")
    workflow.add_conditional_edges("planner", map_analyses, ["analyzer"])
    workflow.add_edge("analyzer", "summarizer")
    workflow.add_edge("summarizer", END)
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer, interrupt_before=["analyzer"])
```

---

## 7. HITL CLI (`main.py`)

```python
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
    doc_structure = parse_pdf_structure(file_path)
    app_graph = build_graph()
    thread_config = {"configurable": {"thread_id": "session_user_1"}}
    initial_state = {"doc_structure": doc_structure, "plan": [], "analyses": []}

    console.print("[bold blue]🤖 AI 正在规划分析任务...[/bold blue]")
    for _ in app_graph.stream(initial_state, thread_config):
        pass

    snapshot = app_graph.get_state(thread_config)
    current_plan = snapshot.values["plan"]

    console.print("\n[yellow]=== AI 提议的分析计划 ===[/yellow]")
    for i, task in enumerate(current_plan):
        console.print(f"{i+1}. 维度: {task.dimension} -> 章节: {task.section_filter}")

    action = Prompt.ask("下一步操作?", choices=["continue", "add", "quit"], default="continue")
    if action == "quit":
        return
    if action == "add":
        new_dim = Prompt.ask("输入新维度名称")
        new_key = Prompt.ask("输入读取章节Key", default="methods")
        new_task = Task(dimension=new_dim, section_filter=new_key, search_query=new_dim)
        app_graph.update_state(thread_config, {"plan": current_plan + [new_task]})

    console.print("🚀 并行分析中...")
    final_output = None
    for event in app_graph.stream(None, thread_config):
        if "summarizer" in event:
            final_output = event["summarizer"]
    if final_output:
        console.print("\n[bold green]=== 最终报告 ===[/bold green]")
        console.print(final_output["final_report"])
```

---

## 8. 评估 (`tests/eval.py`)

基于 LangSmith KV 数据集的自动化评估，使用 `load_evaluator("labeled_criteria")` 或自定义 LLM-as-a-judge。
