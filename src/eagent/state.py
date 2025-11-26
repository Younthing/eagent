import operator
from typing import Annotated, Dict, List

from typing_extensions import TypedDict
from pydantic import BaseModel, Field


class Task(BaseModel):
    """Planner-produced task with context slicing hints."""

    dimension: str = Field(description="分析维度，如 'Methodology'")
    section_filter: str = Field(
        description="需要读取的文档章节Key，例如 'methods' 或 'results'"
    )
    search_query: str = Field(
        description="如果找不到章节，用于向量检索的查询词"
    )


class AnalysisResult(BaseModel):
    dimension: str
    content: str
    is_valid: bool = Field(default=True, description="标记内容是否有效")
    retry_count: int = Field(default=0)


class AgentState(TypedDict):
    # 输入：结构化后的文档 (Section Name -> Content)
    doc_structure: Dict[str, str]
    # 中间状态
    plan: List[Task]
    # 输出结果 (并行追加)
    analyses: Annotated[List[AnalysisResult], operator.add]
    final_report: str
