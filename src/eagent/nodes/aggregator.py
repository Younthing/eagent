from eagent.state import AgentState


def aggregator_node(state: AgentState):
    texts = [
        f"## {a.dimension}\n{a.content}"
        for a in state.get("analyses", [])
        if a.is_valid
    ]
    return {"final_report": "\n\n".join(texts)}
