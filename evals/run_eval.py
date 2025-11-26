from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langsmith import evaluate
from langsmith.schemas import Example, Run

from eagent.graph import build_graph
from eagent.utils.parsing import parse_pdf_structure


async def agent_target(inputs: dict):
    """将 Dataset 输入映射到 Graph 输入，并返回最终结果。"""
    doc_structure = inputs.get("doc_structure")
    if not doc_structure and "raw_content" in inputs:
        doc_structure = parse_pdf_structure(inputs["raw_content"])

    graph = build_graph()
    result = await graph.ainvoke(
        {"doc_structure": doc_structure, "plan": [], "analyses": []}
    )
    return result.get("final_report", "")


class ScoreSchema(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str


async def correctness_evaluator(run: Run, example: Example) -> dict:
    judge_llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
    agent_output = run.outputs
    expected = example.outputs.get("expected_facts", "")

    prompt = ChatPromptTemplate.from_template(
        "你是一个评分专家。\n\n"
        "参考事实: {expected}\n"
        "Agent 生成报告: {actual}\n\n"
        "请判断生成的报告是否包含了参考事实中的关键信息。\n"
        "请返回一个 0 到 1 之间的分数，并说明理由。"
    )

    chain = prompt | judge_llm.with_structured_output(ScoreSchema)
    response: ScoreSchema = await chain.ainvoke(
        {"expected": expected, "actual": agent_output}
    )

    bounded_score = max(0.0, min(response.score, 1.0))

    return {"key": "accuracy", "score": bounded_score, "comment": response.reasoning}


if __name__ == "__main__":
    dataset_name = "Literature Agent Test Set"

    evaluate(
        agent_target,
        data=dataset_name,
        evaluators=[correctness_evaluator],
        experiment_prefix="lit-agent-v2",
        max_concurrency=4,
    )
