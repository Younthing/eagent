## Literature Agent (LangGraph 示例)

并行 Map-Reduce 架构的文献分析智能体示例，包含 LangChain Hub 提示词、LangSmith 追踪、上下文切片、节点重试与 HITL 控制。

### 快速开始
- 安装依赖：`uv pip install -e ".[test]"` 或使用 `pip`。
- 复制环境变量：`cp .env.example .env` 并填入 API Key。
- 运行 CLI：`python main.py --model openai:gpt-4o --temperature 0.0`

### 关键特性
- LangGraph 并行 fan-out/fan-in，支持 interrupt_before + MemorySaver 实现 HITL。
- Prompt Hub 拉取，失败自动回退本地模板。
- Worker 节点内置重试、校验与占位回退，避免整体中断。
- LangSmith `traceable` 解析器与 KV 评测脚本。
