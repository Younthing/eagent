# Literature Agent Project Documentation

一个基于 LangGraph 的文献分析智能体项目示例。该项目遵循生产级标准，包含完整的配置管理、异步支持、通用模型封装、LangSmith 评测以及单元测试最佳实践。

---

## 1. 目录结构

```text
eagent/
├── .env.example                # 环境变量模版
├── pyproject.toml              # 项目依赖与元数据
├── main.py                     # [入口] CLI (Typer + Asyncio)
├── src/
│   └── eagent/
│       ├── __init__.py
│       ├── config.py           # 静态环境配置 (Pydantic V2)
│       ├── configuration.py    # 运行时动态配置 (LangGraph Configurable)
│       ├── factory.py          # 通用 LLM 工厂 (init_chat_model)
│       ├── state.py            # Graph State 定义
│       ├── graph.py            # LangGraph 构建
│       ├── utils/
│       │   └── doc_processor.py
│       └── nodes/              # 业务逻辑节点 (Async)
│           ├── __init__.py
│           ├── planner.py
│           ├── worker.py
│           └── aggregator.py
├── tests/                      # 测试套件
│   ├── conftest.py             # Pytest Fixtures
│   ├── unit/
│   │   └── test_planner.py     # 单元测试 (Mock LLM)
│   └── integration/
│       └── test_graph.py       # 集成测试
└── evals/                      # LangSmith 评测脚本
    ├── __init__.py
    ├── setup_dataset.py
    └── run_eval.py
```

---

## 2. 基础配置

### 2.1 `pyproject.toml`

```toml
[project]
name = "literature-agent"
version = "0.1.0"
description = "Production-ready LangGraph agent example"
requires-python = ">=3.10"
dependencies = [
    "langchain>=0.3.0",
    "langchain-core",
    "langchain-openai",
    "langchain-anthropic",
    "langgraph",
    "langsmith",
    "pydantic>=2",
    "pydantic-settings>=2",
    "typer[all]",
    "rich",
    "python-dotenv",
]

[project.optional-dependencies]
test = [
    "pytest",
    "pytest-asyncio",
    "pytest-mock"
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 2.2 `.env.example`

```bash
# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...

# LangSmith / Tracing
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2-...
LANGCHAIN_PROJECT=literature-agent

# Default Agent Settings
AGENT_DEFAULT_MODEL=openai:gpt-4o
AGENT_DEFAULT_TEMPERATURE=0.0
```

---

## 3. 核心源码 (`src/eagent`)

### 3.1 `src/eagent/config.py` (环境配置)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 默认模型 (格式 provider:model_name)
    default_model: str = "openai:gpt-4o"
    default_temperature: float = 0.0

    # LangSmith
    langchain_tracing_v2: bool = False
    langchain_project: str = "literature-agent"

    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
```

### 3.2 `src/eagent/configuration.py` (运行时配置)

```python
from dataclasses import dataclass, field
from langchain_core.runnables import RunnableConfig
from eagent.config import settings


@dataclass(kw_only=True)
class GraphConfig:
    """允许在 invoke 时通过 configurable 字典动态覆盖的参数。"""
    model_name: str = field(default=settings.default_model)
    temperature: float = field(default=settings.default_temperature)

    @classmethod
    def from_runnable_config(cls, config: RunnableConfig | None = None) -> "GraphConfig":
        configurable = (config or {}).get("configurable", {})
        return cls(
            model_name=configurable.get("model_name", settings.default_model),
            temperature=configurable.get("temperature", settings.default_temperature),
        )
```

### 3.3 `src/eagent/factory.py` (模型工厂)

```python
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from eagent.configuration import GraphConfig


def get_model(config: GraphConfig) -> BaseChatModel:
    """通用模型初始化，支持 openai:gpt-4o, anthropic:claude-3-5-sonnet 等。"""
    if ":" in config.model_name:
        provider, model_name = config.model_name.split(":", 1)
    else:
        provider, model_name = "openai", config.model_name

    return init_chat_model(
        model_name,
        model_provider=provider,
        temperature=config.temperature
    )
```

### 3.4 `src/eagent/state.py` (状态定义)

```python
import operator
from typing import Annotated, List, TypedDict
from pydantic import BaseModel, Field

# --- Pydantic Models ---

class AnalysisTask(BaseModel):
    dimension: str = Field(..., description="分析维度，如'方法论'")
    target_section: str = Field(..., description="关注的文档片段key")
    description: str = Field(..., description="具体指令")

class Plan(BaseModel):
    tasks: List[AnalysisTask]

class AnalysisResult(BaseModel):
    dimension: str
    score: int
    findings: str

# --- Graph State ---

class AgentState(TypedDict, total=False):
    # 输入
    raw_content: str
    structured_doc: dict[str, str]
    
    # 编排
    plan: Plan
    
    # 输出 (并行规约)
    results: Annotated[List[AnalysisResult], operator.add]
    final_report: str
```

### 3.5 `src/eagent/utils/doc_processor.py`

```python
def parse_document_structure(text: str) -> dict[str, str]:
    """模拟文档分段解析。"""
    return {
        "abstract": text[:500] if len(text) > 500 else text,
        "full": text,
    }

def get_relevant_context(doc: dict[str, str], section_key: str) -> str:
    """返回指定分段或全文作为上下文。"""
    return doc.get(section_key, doc.get("full", ""))
```

---

## 4. 节点实现 (`src/eagent/nodes`)

### 4.1 `src/eagent/nodes/planner.py`

```python
import logging
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate

from eagent.state import AgentState, Plan
from eagent.factory import get_model
from eagent.configuration import GraphConfig

logger = logging.getLogger(__name__)

PLANNER_PROMPT = ChatPromptTemplate.from_template(
    "阅读以下摘要并生成分析计划：\n{abstract}"
)

async def planner_node(state: AgentState, config: RunnableConfig) -> dict:
    conf = GraphConfig.from_runnable_config(config)
    llm = get_model(conf)
    
    abstract = state.get("structured_doc", {}).get("abstract", "")
    
    chain = PLANNER_PROMPT | llm.with_structured_output(Plan)
    plan: Plan = await chain.ainvoke({"abstract": abstract})
    
    logger.info("Planner generated %d tasks (Model: %s)", len(plan.tasks), conf.model_name)
    return {"plan": plan}
```

### 4.2 `src/eagent/nodes/worker.py`

```python
import logging
from typing import TypedDict
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate

from eagent.state import AnalysisTask, AnalysisResult
from eagent.factory import get_model
from eagent.configuration import GraphConfig
from eagent.utils.doc_processor import get_relevant_context

logger = logging.getLogger(__name__)

class WorkerInput(TypedDict):
    task: AnalysisTask
    structured_doc: dict[str, str]

WORKER_PROMPT = ChatPromptTemplate.from_template(
    "维度: {dimension}\n指令: {instruction}\n内容: {context}"
)

async def worker_node(state: WorkerInput, config: RunnableConfig) -> dict:
    conf = GraphConfig.from_runnable_config(config)
    llm = get_model(conf)
    
    task = state["task"]
    context = get_relevant_context(state["structured_doc"], task.target_section)
    
    try:
        chain = WORKER_PROMPT | llm.with_structured_output(AnalysisResult)
        result = await chain.ainvoke({
            "dimension": task.dimension,
            "instruction": task.description,
            "context": context
        })
    except Exception as exc:
        logger.exception("Worker failed for %s", task.dimension)
        # 容错处理：返回占位结果，保证聚合数量闭环
        result = AnalysisResult(
            dimension=task.dimension, 
            score=0, 
            findings=f"Error analyzing section: {exc}"
        )
    
    # 补全 Pydantic 缺失字段 (如果 LLM 未返回)
    result.dimension = task.dimension
    
    return {"results": [result]}
```

### 4.3 `src/eagent/nodes/aggregator.py`

```python
import logging
from langchain_core.runnables import RunnableConfig
from langchain_core.prompts import ChatPromptTemplate

from eagent.state import AgentState
from eagent.factory import get_model
from eagent.configuration import GraphConfig

logger = logging.getLogger(__name__)

REPORT_PROMPT = ChatPromptTemplate.from_template(
    "根据以下分析结果撰写总结报告:\n{results_text}"
)

async def aggregator_node(state: AgentState, config: RunnableConfig) -> dict:
    conf = GraphConfig.from_runnable_config(config)
    llm = get_model(conf)
    
    results = state.get("results", [])
    if not results:
        logger.warning("Aggregator received no results; returning empty report.")
        return {"final_report": "No results to aggregate."}
    
    text_blobs = [f"## {r.dimension}\nFindings: {r.findings}" for r in results]
    
    response = await (REPORT_PROMPT | llm).ainvoke({"results_text": "\n\n".join(text_blobs)})
    
    logger.info("Report generated.")
    return {"final_report": response.content}
```

---

## 5. 图构建 (`src/eagent/graph.py`)

```python
from langgraph.graph import StateGraph
from langgraph.constants import Send, START, END

from eagent.state import AgentState
from eagent.nodes.planner import planner_node
from eagent.nodes.worker import worker_node
from eagent.nodes.aggregator import aggregator_node
from eagent.utils.doc_processor import parse_document_structure

async def doc_parser(state: AgentState) -> dict:
    return {"structured_doc": parse_document_structure(state["raw_content"])}

def map_tasks(state: AgentState):
    """Fan-out to workers."""
    return [
        Send("worker", {"task": t, "structured_doc": state["structured_doc"]})
        for t in state["plan"].tasks
    ]

def check_finished(state: AgentState):
    """检查并行 Worker 是否全部完成，只在收敛时进入 aggregator。"""
    plan = state.get("plan")
    results = state.get("results", [])
    
    if not plan or not plan.tasks:
        return END
    
    if len(results) >= len(plan.tasks):
        return "aggregator"
    
    return END

def build_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("parser", doc_parser)
    workflow.add_node("planner", planner_node)
    workflow.add_node("worker", worker_node)
    workflow.add_node("aggregator", aggregator_node)

    workflow.add_edge(START, "parser")
    workflow.add_edge("parser", "planner")
    workflow.add_conditional_edges("planner", map_tasks)
    workflow.add_conditional_edges("worker", check_finished)
    workflow.add_edge("aggregator", END)

    return workflow
```

---

## 6. 测试 (`tests/`)

### 6.1 `tests/conftest.py`

```python
import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_llm_structured():
    """创建一个 Mock 对象，模拟 .with_structured_output().ainvoke() 的行为"""
    def _create_mock(return_value):
        mock_llm = MagicMock()
        mock_runnable = MagicMock()
        mock_runnable.ainvoke.return_value = return_value
        mock_llm.with_structured_output.return_value = mock_runnable
        return mock_llm
    return _create_mock
```

### 6.2 `tests/unit/test_planner.py`

```python
import pytest
from unittest.mock import patch
from eagent.nodes.planner import planner_node
from eagent.state import Plan, AnalysisTask

@pytest.mark.asyncio
async def test_planner_node_success(mock_llm_structured):
    # 1. 准备 Mock 数据
    expected_plan = Plan(tasks=[
        AnalysisTask(dimension="Test", target_section="abstract", description="Do it")
    ])
    
    # 2. Patch factory.get_model
    with patch("eagent.nodes.planner.get_model") as mock_get_model:
        mock_get_model.return_value = mock_llm_structured(expected_plan)
        
        # 3. 执行 Node
        state = {"structured_doc": {"abstract": "paper content"}}
        config = {"configurable": {"model_name": "mock-model"}}
        
        output = await planner_node(state, config)
        
        # 4. 断言
        assert output["plan"] == expected_plan
        assert len(output["plan"].tasks) == 1
```

### 6.3 `tests/integration/test_graph.py`

```python
from eagent.graph import build_graph

def test_graph_compilation():
    graph = build_graph()
    app = graph.compile()
    assert app is not None
    # 验证图结构完整性
    assert "planner" in app.nodes
    assert "worker" in app.nodes
```

---

## 7. 入口文件 (`main.py`)

```python
import asyncio
import typer
from dotenv import load_dotenv
from rich.console import Console
from eagent.graph import build_graph

app = typer.Typer()
console = Console()

@app.command()
def analyze(
    text: str = "这是一个关于人工智能的文献摘要...",
    model: str = "openai:gpt-4o",
    temperature: float = 0.0
):
    """
    运行 Agent 分析任务。
    示例: python main.py --model ollama:llama3
    """
    load_dotenv()
    async def _run():
        graph = build_graph().compile()
        
        # 运行时配置覆盖
        config = {
            "configurable": {
                "model_name": model,
                "temperature": temperature
            }
        }
        
        initial_state = {"raw_content": text, "results": []}
        
        console.print(f"[bold green]Starting analysis using {model}...[/bold green]")
        
        final_state = await graph.ainvoke(initial_state, config=config)
        
        console.print("\n[bold blue]=== FINAL REPORT ===[/bold blue]")
        console.print(final_state.get("final_report", "No report generated."))

    asyncio.run(_run())

if __name__ == "__main__":
    app()
```

---

## 8. 评测系统 (`evals/`)

基于 LangSmith `evaluate` API 的自动化评测流程。

### 8.1 目录结构更新

```text
eagent/
├── ...
└── evals/
    ├── __init__.py
    ├── setup_dataset.py    # [工具] 创建/上传测试数据集
    └── run_eval.py         # [脚本] 运行评测
```

### 8.2 `evals/setup_dataset.py` (数据集准备)

```python
from langsmith import Client

client = Client()

dataset_name = "Literature Agent Test Set"

# 示例数据：包含输入文本和期望的关键结论
examples = [
    {
        "inputs": {
            "raw_content": (
                "摘要：本文提出了Transformer架构，通过自注意力机制..."
                "结论：该模型在机器翻译任务上得分为 28.4 BLEU。"
            )
        },
        "outputs": {
            "expected_facts": "Transformer架构; 自注意力机制; BLEU 28.4"
        }
    },
    {
        "inputs": {
            "raw_content": "摘要：我们研究了光合作用在低光照下的效率..."
        },
        "outputs": {
            "expected_facts": "光合作用; 低光照; 效率研究"
        }
    }
]

def create_dataset():
    if client.has_dataset(dataset_name=dataset_name):
        print(f"数据集 '{dataset_name}' 已存在。")
        return

    dataset = client.create_dataset(dataset_name=dataset_name)
    client.create_examples(
        inputs=[e["inputs"] for e in examples],
        outputs=[e["outputs"] for e in examples],
        dataset_id=dataset.id,
    )
    print(f"数据集 '{dataset_name}' 创建成功。")

if __name__ == "__main__":
    create_dataset()
```

### 8.3 `evals/run_eval.py` (评测逻辑)

```python
import asyncio
from pydantic import BaseModel, Field
from langsmith import evaluate
from langsmith.schemas import Run, Example
from langchain_core.prompts import ChatPromptTemplate

from eagent.graph import build_graph
from eagent.factory import get_model
from eagent.configuration import GraphConfig

# 1. 定义待评测的系统 (Target)
async def agent_target(inputs: dict):
    """将 Dataset 输入映射到 Graph 输入，并返回最终结果。"""
    graph = build_graph().compile()
    # 使用 invoke/ainvoke
    result = await graph.ainvoke({
        "raw_content": inputs["raw_content"],
        "results": [] # 初始化空列表
    })
    return result.get("final_report", "")

# 2. 定义评估器 (Evaluators)
class ScoreSchema(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str

async def correctness_evaluator(run: Run, example: Example) -> dict:
    """LLM-as-a-judge: 对比 Agent 生成报告与 Dataset 参考答案。"""
    
    # 获取 Judge 模型 (可以使用专门的配置，这里复用默认)
    conf = GraphConfig(model_name="openai:gpt-4o", temperature=0.0)
    judge_llm = get_model(conf)

    agent_output = run.outputs
    expected = example.outputs.get("expected_facts", "")

    # 构造评分 Prompt
    prompt = ChatPromptTemplate.from_template(
        "你是一个评分专家。\n\n"
        "参考事实: {expected}\n"
        "Agent 生成报告: {actual}\n\n"
        "请判断生成的报告是否包含了参考事实中的关键信息。\n"
        "请返回一个 0 到 1 之间的分数，并说明理由。"
    )

    chain = prompt | judge_llm.with_structured_output(ScoreSchema)
    response: ScoreSchema = await chain.ainvoke({
        "expected": expected,
        "actual": agent_output
    })

    bounded_score = max(0.0, min(response.score, 1.0))

    return {
        "key": "accuracy",
        "score": bounded_score,
        "comment": response.reasoning
    }

# 3. 运行评测
if __name__ == "__main__":
    dataset_name = "Literature Agent Test Set"
    
    evaluate(
        agent_target,
        data=dataset_name,
        evaluators=[correctness_evaluator],
        experiment_prefix="lit-agent-v1",
        max_concurrency=4,  # 并发控制
    )
```
