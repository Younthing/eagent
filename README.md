## Literature Agent (LangGraph 示例)

并行 Map-Reduce 架构的文献分析智能体示例，包含 LangChain Hub 提示词、LangSmith 追踪、上下文切片、节点重试与 HITL 控制。

### 快速开始
- 安装依赖：`uv sync`（如需运行测试或评估，额外执行 `uv sync --extra test` 安装测试依赖）。
- 复制环境变量：`cp .env.example .env`，并根据 LangGraph 观察性文档配置 `LANGSMITH_API_KEY`、`LANGSMITH_ENDPOINT`、`LANGSMITH_PROJECT`、`LANGSMITH_TRACING=true`。
- 运行 CLI：`uv run eagent`

### 关键特性
- LangGraph 并行 fan-out/fan-in，支持 interrupt_before + MemorySaver 实现 HITL。
- Worker 节点内置重试、校验与占位回退，避免整体中断。
- LangSmith `traceable` 解析器与 KV 评测脚本。
