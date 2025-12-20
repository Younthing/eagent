from typing import List

from pydantic import BaseModel

from eagent.llm import get_default_llm
from eagent.prompts import planner_prompt
from eagent.state import AgentState, Task

llm = get_default_llm()


class PlanningOutput(BaseModel):
    tasks: List[Task]


def plan_node(state: AgentState):
    doc_keys = [
        key for key, value in state["doc_structure"].items() if isinstance(value, str)
    ]
    chain = planner_prompt | llm.with_structured_output(PlanningOutput)
    result: PlanningOutput = chain.invoke({"doc_keys": str(doc_keys)})
    return {"plan": result.tasks}
