一个**结构清晰、生产级、可扩展、易于评估和调试且符合 Python 最佳实践**的示例langgraph项目
---

## 1. 项目目录结构（精修版）

```text
eagent/
├── .env.example                # 环境变量示例（包含 LangSmith）
├── pyproject.toml              # 依赖 & 项目信息
├── README.md                   # 使用说明（略写）
├── main.py                     # [入口] Typer CLI + HITL
├── evals/
│   └── evaluate_accuracy.py    # 评测脚本（示例）
└── src/
    └── eagent/       # 项目主包
        ├── __init__.py
        ├── config.py           # Pydantic Settings + LangSmith 配置
        ├── logging_config.py   # logging 统一配置
        ├── llm.py              # LLM 工厂（统一模型配置）
        ├── state.py            # Graph State & Pydantic Schemas
        ├── graph.py            # LangGraph 构建（Nodes + Edges）
        ├── prompts/
        │   ├── planner_prompt.md
        │   └── aggregator_prompt.md
        ├── utils/
        │   └── doc_processor.py
        └── nodes/
            ├── __init__.py
            ├── planner.py
            ├── worker.py
            └── aggregator.py
```

---

## 2. 配置相关

### 2.1 `.env.example`

```bash
# OpenAI / LangChain / LangSmith 基本配置
OPENAI_API_KEY=your-openai-key

# LangSmith / LangChain Tracing (强烈建议开启)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_PROJECT=literature-agent

# Literature Agent 自身配置（通过 Pydantic Settings 读取）
AGENT_OPENAI_MODEL=gpt-4o
AGENT_OPENAI_TEMPERATURE=0.0
```

---

### 2.2 `pyproject.toml`（简化示例）

```toml
[project]
name = "literature-agent"
version = "0.1.0"
description = "Literature analysis agent using LangGraph + LangSmith"
requires-python = ">=3.10"
dependencies = [
    "langchain-core",
    "langchain-openai",
    "langgraph",
    "langsmith",
    "pydantic>=2",
    "pydantic-settings>=2",
    "typer[all]",
    "rich",
]

[project.scripts]
literature-agent = "main:app"
```

---

### 2.3 `src/eagent/config.py`

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.0

    # LangSmith / LangChain Tracing
    langchain_tracing_v2: bool = True
    langchain_project: str = "literature-agent"

    class Config:
        env_prefix = "AGENT_"
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

---

### 2.4 `src/eagent/logging_config.py`

```python
import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """统一初始化 logging，CLI & 评测脚本都可以调用。"""
    root = logging.getLogger()
    if root.handlers:
        # 已经配置过，就不重复添加
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root.setLevel(level)
    root.addHandler(handler)
```

---

### 2.5 `src/eagent/llm.py`

统一 LLM 工厂，方便切模型、加超时/重试等。

```python
from langchain_openai import ChatOpenAI

from .config import settings


def get_llm(temperature: float | None = None) -> ChatOpenAI:
    """主任务用 LLM."""
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=temperature if temperature is not None else settings.openai_temperature,
    )


def get_judge_llm() -> ChatOpenAI:
    """评测 / LLM-as-a-judge 用 LLM，通常可以稍微放开一点温度."""
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0.2,
    )
```

---

## 3. State & 文档处理

### 3.1 `src/eagent/state.py`

```python
import operator
from typing import Annotated, List
from typing_extensions import NotRequired
from typing import TypedDict

from pydantic import BaseModel, Field


# --- Pydantic Models (结构化输入/输出) ---


class AnalysisTask(BaseModel):
    """Planner 生成的单个任务."""
    dimension: str = Field(..., description="分析维度，如 '方法论'")
    target_section: str = Field(
        ...,
        description="需要关注的文档片段，如 'methodology', 'abstract'",
    )
    description: str = Field(..., description="给 Worker 的具体指令")


class Plan(BaseModel):
    tasks: List[AnalysisTask]


class AnalysisResult(BaseModel):
    """Worker 返回的分析结果."""
    dimension: str
    score: int = Field(..., description="评分 1-10")
    findings: str = Field(..., description="核心发现")
    evidence: str = Field(..., description="原文引用作为证据")


# --- LangGraph State ---


class AgentState(TypedDict, total=False):
    # 输入
    raw_content: str
    structured_doc: dict[str, str]

    # 中间状态
    plan: Plan
    total_tasks: int

    # 并行累加 (operator.add 支持多个 worker 写入)
    results: Annotated[List[AnalysisResult], operator.add]

    # 输出
    final_report: str
```

---

### 3.2 `src/eagent/utils/doc_processor.py`

```python
from typing import Dict


def parse_document_structure(text: str) -> Dict[str, str]:
    """
    简单的模拟解析器。

    生产环境建议：
    - 使用 Unstructured / pypdf 等工具解析章节
    - 保证返回的 key 稳定，如: abstract, methodology, results, full
    """
    return {
        "abstract": text[:500],
        "methodology": text,
        "results": text[-1000:],
        "full": text,
    }


def get_relevant_context(structured_doc: Dict[str, str], section_key: str) -> str:
    """根据 Plan 指定的 key 获取相关文本."""
    if section_key in structured_doc:
        return structured_doc[section_key]
    # fallback
    return structured_doc.get("full", "")
```

---

## 4. 节点实现

### 4.1 Prompt 模板（可选本地）

`src/eagent/prompts/planner_prompt.md`（示例）：

```markdown
你是一个严谨的文献综述规划专家。

阅读以下文献的摘要内容：

{abstract}

请基于摘要给出一个分析计划（Plan），要求：
- 至少包含 3 个 AnalysisTask
- 每个 task 指明：dimension, target_section, description
- target_section 必须是以下之一：abstract, methodology, results, full
```

`src/eagent/prompts/aggregator_prompt.md`（示例）：

```markdown
你是一名资深学术写作者。

根据以下各维度的分析结果，撰写一份结构清晰、专业的文献综述报告。

分析结果：
{results_text}
```

---

### 4.2 `src/eagent/nodes/planner.py`

```python
import logging

from langchain import hub
from langchain_core.prompts import ChatPromptTemplate

from eagent.state import AgentState, Plan
from eagent.llm import get_llm

logger = logging.getLogger(__name__)

# 优先从 LangSmith Hub 拉取 Prompt
try:
    PLANNER_PROMPT = hub.pull("your-org/literature-planner")
    logger.info("Loaded planner prompt from LangSmith Hub.")
except Exception as e:  # noqa: BLE001
    logger.warning(
        "Failed to load planner prompt from Hub, using local fallback. Error: %s",
        e,
    )
    PLANNER_PROMPT = ChatPromptTemplate.from_template(
        "你是一个文献分析 Planner。\n\n"
        "阅读以下文献摘要：\n{abstract}\n\n"
        "请输出一个分析计划 Plan（结构化 JSON），要求：\n"
        "- 至少包含 3 个 AnalysisTask\n"
        "- 每个 task 包含 dimension, target_section, description\n"
        "- target_section 必须是: 'abstract', 'methodology', 'results', 'full' 之一"
    )

llm = get_llm(temperature=0.0)


def planner_node(state: AgentState) -> dict:
    logger.info("[Planner] Generating analysis plan...")
    abstract = state.get("structured_doc", {}).get("abstract", "")

    structured_llm = llm.with_structured_output(Plan)
    chain = PLANNER_PROMPT | structured_llm

    plan: Plan = chain.invoke({"abstract": abstract})
    logger.info("[Planner] Generated %d tasks.", len(plan.tasks))

    return {
        "plan": plan,
        "total_tasks": len(plan.tasks),
    }
```

---

### 4.3 `src/eagent/nodes/worker.py`

```python
import logging
from typing import TypedDict

from eagent.state import AnalysisTask, AnalysisResult
from eagent.llm import get_llm
from eagent.utils.doc_processor import get_relevant_context

logger = logging.getLogger(__name__)

llm = get_llm(temperature=0.0)


class WorkerState(TypedDict):
    task: AnalysisTask
    structured_doc: dict[str, str]


def worker_node(state: WorkerState) -> dict:
    """
    注意：这里的 state 是通过 Send payload 注入的，
    不是全局 AgentState，而是 {"task": ..., "structured_doc": ...}
    """
    task = state["task"]
    doc = state["structured_doc"]

    logger.info("[Worker] Analyzing dimension: %s", task.dimension)

    context = get_relevant_context(doc, task.target_section)

    prompt = (
        f"你是一个严谨的分析师。\n\n"
        f"分析维度：{task.dimension}\n"
        f"具体指令：{task.description}\n\n"
        f"参考文本：\n{context}\n"
    )

    structured_llm = llm.with_structured_output(AnalysisResult)
    result: AnalysisResult = structured_llm.invoke(prompt)

    # 防御性校验 + 补齐字段
    result.dimension = task.dimension
    if not (1 <= result.score <= 10):
        logger.warning(
            "[Worker] Score %s out of range, fallback to 5.",
            result.score,
        )
        result.score = 5

    return {"results": [result]}
```

---

### 4.4 `src/eagent/nodes/aggregator.py`

```python
import logging

from langchain_core.prompts import ChatPromptTemplate

from eagent.state import AgentState
from eagent.llm import get_llm

logger = logging.getLogger(__name__)

llm = get_llm(temperature=0.2)

AGGREGATOR_PROMPT = ChatPromptTemplate.from_template(
    "你是一名资深学术写作者。\n\n"
    "根据以下各维度的分析结果，撰写一份结构清晰、专业的文献综述报告。\n\n"
    "{results_text}"
)


def aggregator_node(state: AgentState) -> dict:
    logger.info("[Aggregator] Synthesizing report...")

    results = state.get("results", [])
    total = state.get("total_tasks", len(results))

    # 如果你希望支持「渐进式」聚合，可以在 len(results) < total 时直接 return {}
    if len(results) < total:
        logger.info(
            "[Aggregator] Only %d/%d results ready, skip final report for now.",
            len(results),
            total,
        )
        return {}

    results_text = "\n\n".join(
        f"## {r.dimension} (Score: {r.score})\n"
        f"Findings: {r.findings}\n"
        f"Evidence: {r.evidence}"
        for r in results
    )

    response = llm.invoke(AGGREGATOR_PROMPT.format(results_text=results_text))

    logger.info("[Aggregator] Final report generated.")
    return {"final_report": response.content}
```

---

## 5. 图构建

### 5.1 `src/eagent/graph.py`

```python
from typing import List

from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send

from eagent.state import AgentState
from eagent.nodes.planner import planner_node
from eagent.nodes.worker import worker_node
from eagent.nodes.aggregator import aggregator_node
from eagent.utils.doc_processor import parse_document_structure


def doc_parser(state: AgentState) -> dict:
    """预处理节点：解析文档结构."""
    struct = parse_document_structure(state["raw_content"])
    return {"structured_doc": struct}


def map_tasks(state: AgentState) -> List[Send]:
    """Dynamic Map：根据 plan fan-out 到多个 worker."""
    plan = state["plan"]
    structured_doc = state["structured_doc"]

    sends: List[Send] = []
    for task in plan.tasks:
        sends.append(
            Send(
                "worker",
                {
                    "task": task,
                    "structured_doc": structured_doc,
                },
            )
        )
    return sends


def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("parser", doc_parser)
    workflow.add_node("planner", planner_node)
    workflow.add_node("worker", worker_node)
    workflow.add_node("aggregator", aggregator_node)

    # Start -> Parser -> Planner
    workflow.add_edge(START, "parser")
    workflow.add_edge("parser", "planner")

    # Planner -> Dynamic Map (Workers)
    # 这里使用 Send，故不需要 path_map 参数
    workflow.add_conditional_edges("planner", map_tasks)

    # Workers -> Aggregator -> End
    workflow.add_edge("worker", "aggregator")
    workflow.add_edge("aggregator", END)

    return workflow
```

---

## 6. CLI + HITL

### 6.1 `main.py`

```python
import uuid
from pathlib import Path

import typer
from rich.console import Console

from eagent.graph import build_graph
from eagent.logging_config import setup_logging

app = typer.Typer()
console = Console()


@app.command()
def analyze(file_path: str):
    """运行文献分析 Agent，包含 Planner HITL。"""
    setup_logging()

    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]File not found:[/red] {file_path}")
        raise typer.Exit(code=1)

    console.print(f"[bold]Loading {file_path}...[/bold]")
    content = path.read_text(encoding="utf-8")

    # 编译图，设置在 planner 后中断
    graph = build_graph().compile(interrupt_after=["planner"])

    initial_inputs = {
        "raw_content": content,
        "results": [],
    }
    thread = {"configurable": {"thread_id": str(uuid.uuid4())}}

    console.print("[yellow]Running Parser & Planner...[/yellow]")

    # 运行到断点
    for event in graph.stream(initial_inputs, thread, stream_mode="values"):
        for node, value in event.items():
            console.log(f"[cyan]{node}[/cyan] -> keys: {list(value.keys())}")

    # 获取状态快照
    state_snapshot = graph.get_state(thread)
    current_plan = state_snapshot.values.get("plan")

    if current_plan is None:
        console.print("[red]Planner did not produce a plan.[/red]")
        raise typer.Exit(code=1)

    console.print("\n[bold green]AI 生成的分析计划:[/bold green]")
    for idx, task in enumerate(current_plan.tasks, start=1):
        console.print(
            f"{idx}. {task.dimension} "
            f"(Focus: {task.target_section})\n    {task.description}"
        )

    # HITL 确认
    confirm = typer.confirm("计划看起来没问题吗？")
    if not confirm:
        console.print("[red]用户终止。[/red]")
        raise typer.Exit()

    console.print(
        "[yellow]Resuming execution (Workers -> Aggregator)...[/yellow]"
    )

    final_report: str | None = None

    # 继续执行（传入 None 表示从中断状态继续）
    for event in graph.stream(None, thread, stream_mode="values"):
        for node, value in event.items():
            console.log(f"[cyan]{node}[/cyan] -> keys: {list(value.keys())}")
            if node == "aggregator" and "final_report" in value:
                final_report = value["final_report"]

    console.print("\n[bold blue]=== FINAL REPORT ===[/bold blue]")
    if final_report:
        console.print(final_report)
    else:
        console.print("[red]No final report found.[/red]")


if __name__ == "__main__":
    app()
```

---

## 7. 评测脚本（含 LangSmith）

### 7.1 `evals/evaluate_accuracy.py`

> 说明：这里给出的是一个**手写 loop + LLM judge** 示例，并把 trace 交给 LangSmith。
> 若要用 LangSmith 的 `client.evaluate` / `run_on_dataset`，可以在此基础上再适配。

```python
import asyncio
from typing import Any, Dict, List

from langsmith import Client

from eagent.graph import build_graph
from eagent.logging_config import setup_logging
from eagent.llm import get_judge_llm

# 模拟 KV 数据集（实际建议从 JSON / LangSmith Dataset 加载）
DATASET: List[Dict[str, Any]] = [
    {
        "input_text": "Paper A content...",
        "expected_kv": {
            "Method": "Transformer",
            "Accuracy": "99%",
        },
    },
    # ... 更多样本
]


def parse_score(text: str) -> float:
    """从 Judge 输出中粗略解析 [0,1] 分数."""
    import re

    match = re.search(r"([01](?:\.\d+)?)", text)
    if not match:
        return 0.0
    return float(match.group(1))


async def run_eval() -> None:
    setup_logging()
    client = Client()
    judge_llm = get_judge_llm()

    graph = build_graph().compile()  # 评测时不需要 interrupt
    print(f"开始评测 {len(DATASET)} 条数据...")

    for idx, item in enumerate(DATASET, start=1):
        raw_content = item["input_text"]
        expected_kv = item["expected_kv"]

        # 1. 运行 Agent
        response = await graph.ainvoke({"raw_content": raw_content, "results": []})
        final_report = response.get("final_report", "")
        structured_results = response.get("results", [])

        # 2. LLM-as-a-judge 评分
        judge_prompt = f"""
Ground Truth (期望提取的关键信息):
{expected_kv}

Agent Generated Report:
{final_report}

请评分一个 0-1 之间的小数：
- 1 表示完全包含且准确
- 0 表示完全不包含

只输出分数本身（如 0.8）。
        """.strip()

        judge_resp = await judge_llm.ainvoke(judge_prompt)
        score_text = judge_resp.content
        score = parse_score(score_text)

        print(
            f"[{idx}/{len(DATASET)}] "
            f"Input: {raw_content[:20]}... | Score: {score:.2f}"
        )

        # 3. （可选）将结果记录到 LangSmith
        # 下面是示意性代码，请根据 LangSmith 当前 SDK 文档调整参数：
        #
        # client.create_run(
        #     name="literature-agent-eval",
        #     inputs={"raw_content": raw_content},
        #     outputs={
        #         "final_report": final_report,
        #         "structured_results": [r.model_dump() for r in structured_results],
        #     },
        #     extra={"expected_kv": expected_kv, "judge_score": score},
        # )

    print("评测完成。")


if __name__ == "__main__":
    asyncio.run(run_eval())
```

---