"""
Plan-and-Execute framework graph builder.

This module provides the framework class and graph building functions
for the Planner-Worker-Reporter architecture.
"""

from typing import Any

from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from mobility_bench.agent.frameworks.base import BaseFramework
from mobility_bench.agent.frameworks.plan_and_execute.nodes import (
    planner_node,
    reporter_node,
    worker_node,
)
from mobility_bench.agent.graph.state import State
from mobility_bench.config.settings import ModelConfig, Settings


def _build_base_graph() -> StateGraph:
    """Build and return the base state graph with all nodes and edges."""
    builder = StateGraph(State)

    # Nodes
    builder.add_node("planner", planner_node)
    builder.add_node("worker_node", worker_node)
    builder.add_node("reporter", reporter_node)

    # Entry and edges
    builder.set_entry_point("planner")
    # Plan system architecture: worker returns to planner for unified management
    builder.add_edge("worker_node", "planner")  # Worker returns to planner
    builder.add_edge("reporter", "__end__")  # Reporter ends the flow

    return builder


def build_graph() -> CompiledStateGraph:
    """Build and return the compiled agent workflow graph."""
    builder = _build_base_graph()
    return builder.compile()


class PlanAndExecuteFramework(BaseFramework):
    """
    Plan-and-Execute framework implementation.

    This framework uses a three-role architecture:
    - Planner: Analyzes user needs and generates structured execution plans
    - Worker: Executes tool calls based on the plan
    - Reporter: Generates final reports from execution results
    """

    def __init__(self, settings: Settings | None = None, model_config: ModelConfig | None = None):
        super().__init__(settings, model_config)
        self._graph: CompiledStateGraph | None = None

    @property
    def name(self) -> str:
        return "plan_and_execute"

    def build_graph(self) -> CompiledStateGraph:
        """Build and return the compiled graph."""
        if self._graph is None:
            # Set up LLM manager with model config before building
            if self.model_config:
                from mobility_bench.agent.roles.llm_manager import set_model_config
                set_model_config(self.model_config)

            self._graph = build_graph()
        return self._graph

    def prepare_initial_state(self, query: str, context: str | None = None, **kwargs) -> dict[str, Any]:
        """
        Prepare initial state for Plan-and-Execute execution.

        Args:
            query: User query string
            context: Optional context information
            **kwargs: Additional state fields (e.g., poi_map)

        Returns:
            Initial state dictionary
        """
        state = {
            "query": query,
            "context": context,
            "messages": [],
            "poi_map": kwargs.get("poi_map", {}),
            "current_plan": None,
            "plan_iterations": 0,
        }

        # Merge any additional kwargs
        for key, value in kwargs.items():
            if key not in state:
                state[key] = value

        return state

    def extract_result(self, final_state: dict[str, Any]) -> dict[str, Any]:
        """
        Extract result from final state.

        Args:
            final_state: Final state after graph execution

        Returns:
            Result dictionary with:
            - plan_result: Final markdown report
            - planner_training_data: Planner execution data
            - worker_training_data: List of worker execution data
            - reporter_training_data: Reporter execution data
            - token_usage: Token usage statistics
        """
        return {
            "plan_result": final_state.get("plan_result", ""),
            "planner_training_data": final_state.get("planner_training_data", {}),
            "worker_training_data": final_state.get("worker_training_data", []),
            "reporter_training_data": final_state.get("reporter_training_data", {}),
            "planner_intent": final_state.get("planner_intent", ""),
            "planner_thinking": final_state.get("planner_thinking", ""),
            "token_usage": {
                "planner": final_state.get("planner_token_usage", {}),
                "worker": final_state.get("worker_token_usage", {}),
                "reporter": final_state.get("reporter_token_usage", {}),
            },
        }
