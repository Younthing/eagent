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
    """尝试从 LangChain Hub 拉取，失败则使用本地默认。"""
    try:
        return hub.pull(repo_id)
    except Exception as exc:
        print(f"⚠️ Warning: Failed to pull prompt {repo_id}, using default. Error: {exc}")
        return default


planner_prompt = get_prompt("my-org/paper-analysis-planner", _DEFAULT_PLANNER)
worker_prompt = get_prompt("my-org/paper-section-analyzer", _DEFAULT_WORKER)
