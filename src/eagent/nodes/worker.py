from eagent.llm import get_default_llm
from eagent.prompts import worker_prompt
from eagent.state import AnalysisResult, Task

llm = get_default_llm()


def extract_context(doc: dict, task: Task) -> str:
    """Context Slicing: exact section first, fallback to truncated full doc."""
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
