"""Execution helpers for running the LangGraph workflow."""

from typing import Dict, List, Optional

from dotenv import load_dotenv

from eagent.graph import build_graph
from eagent.state import Task

load_dotenv()


class AnalysisSession:
    """Encapsulates LangGraph execution with simple hooks for HITL flows."""

    def __init__(self, doc_structure: Dict[str, str], thread_id: str = "session_user_1"):
        self.doc_structure = doc_structure
        self.thread_config = {"configurable": {"thread_id": thread_id}}
        self.graph = build_graph()
        self._plan: List[Task] = []
        self._planned = False

    @property
    def plan(self) -> List[Task]:
        return list(self._plan)

    def generate_plan(self) -> List[Task]:
        if self._planned:
            return self.plan

        initial_state = {
            "doc_structure": self.doc_structure,
            "plan": [],
            "analyses": [],
        }

        for _ in self.graph.stream(initial_state, self.thread_config):
            pass

        snapshot = self.graph.get_state(self.thread_config)
        if not snapshot.values:
            self._plan = []
            self._planned = True
            return []

        self._plan = list(snapshot.values.get("plan", []))
        self._planned = True
        return self.plan

    def update_plan(self, tasks: List[Task]) -> None:
        if not self._planned:
            self.generate_plan()

        self._plan = list(tasks)
        self.graph.update_state(self.thread_config, {"plan": self._plan})

    def run(self) -> Optional[str]:
        if not self._planned:
            self.generate_plan()

        final_report: Optional[str] = None
        for event in self.graph.stream(None, self.thread_config):
            if "summarizer" in event:
                final_report = event["summarizer"].get("final_report")

        return final_report
