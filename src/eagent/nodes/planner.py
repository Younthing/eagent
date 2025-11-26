from typing import List

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from eagent.prompts import planner_prompt
from eagent.state import AgentState, Task

llm = ChatOpenAI(model="gpt-4o", temperature=0)


class PlanningOutput(BaseModel):
    tasks: List[Task]


def plan_node(state: AgentState):
    doc_keys = list(state["doc_structure"].keys())
    chain = planner_prompt | llm.with_structured_output(PlanningOutput)
    result: PlanningOutput = chain.invoke({"doc_keys": str(doc_keys)})
    return {"plan": result.tasks}
