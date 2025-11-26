from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import Send, START, END
from langgraph.graph import StateGraph

from eagent.nodes.aggregator import aggregator_node
from eagent.nodes.planner import plan_node
from eagent.nodes.worker import worker_node
from eagent.state import AgentState, Task


def map_analyses(state: AgentState):
    """动态 Map: 基于 plan 生成并发任务"""
    return [
        Send("analyzer", {"task": task, "doc_structure": state["doc_structure"]})
        for task in state["plan"]
    ]


def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("planner", plan_node)
    workflow.add_node("analyzer", worker_node)
    workflow.add_node("summarizer", aggregator_node)

    workflow.add_edge(START, "planner")
    workflow.add_conditional_edges("planner", map_analyses, ["analyzer"])
    workflow.add_edge("analyzer", "summarizer")
    workflow.add_edge("summarizer", END)

    checkpointer = MemorySaver()

    return workflow.compile(checkpointer=checkpointer, interrupt_before=["analyzer"])
