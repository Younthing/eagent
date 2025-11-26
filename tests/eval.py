import asyncio

from langchain.evaluation import load_evaluator
from langsmith import Client

from eagent.graph import build_graph
from eagent.llm import get_default_llm

DATASET_NAME = "Literature-KV-Test"
KV_EXAMPLES = [
    {
        "inputs": {
            "doc_structure": {
                "methods": "We used a standard Transformer model.",
                "results": "Accuracy is 95%.",
            }
        },
        "outputs": {
            "expected_method": "Transformer",
            "expected_metric": "95%",
        },
    }
]

eval_llm = get_default_llm()


def correct_extraction_evaluator(run, example):
    final_report = run.outputs.get("final_report", "")
    ground_truth = str(example.outputs)
    prompt = f"""
    作为一名严格的评分员，请判断提取内容是否包含了标准答案中的关键事实。

    提取内容: {final_report}
    标准答案: {ground_truth}

    仅返回分数 (0 到 1 之间)，1 表示完全包含，0 表示完全错误。
    """
    response = eval_llm.invoke(prompt)
    try:
        score = float(response.content.strip())
    except Exception:
        score = 0.0
    return {"key": "correctness", "score": score}


async def main():
    client = Client()

    if not client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.create_dataset(DATASET_NAME)
        client.create_examples(
            inputs=[e["inputs"] for e in KV_EXAMPLES],
            outputs=[e["outputs"] for e in KV_EXAMPLES],
            dataset_id=dataset.id,
        )
        print(f"Created dataset: {DATASET_NAME}")

    graph = build_graph()

    await client.arun_on_dataset(
        dataset_name=DATASET_NAME,
        llm_or_chain_factory=lambda: graph,
        evaluation=load_evaluator("labeled_criteria", criteria="correctness"),
        # custom_evaluators=[correct_extraction_evaluator],
    )

    print("\nEvaluation Complete. Check LangSmith UI for details.")


if __name__ == "__main__":
    asyncio.run(main())
