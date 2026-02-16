"""
Graph builder for the mobility agent system.

This module provides functions to build and compile the LangGraph
workflow for different agent frameworks (Plan-and-Execute, ReAct, etc.).
"""

from typing import Any

from langgraph.graph.state import CompiledStateGraph

from mobility_bench.agent.graph.state import State
from mobility_bench.config.settings import ModelConfig, Settings


# Current framework instance
_current_framework = None


def build_graph(
    framework: str = "plan_and_execute",
    settings: Settings | None = None,
    model_config: ModelConfig | None = None,
) -> CompiledStateGraph:
    """
    Build and return the compiled agent workflow graph for the specified framework.

    Args:
        framework: Framework type ("plan_and_execute" or "react")
        settings: Global settings object
        model_config: Specific model configuration

    Returns:
        Compiled LangGraph instance
    """
    global _current_framework

    from mobility_bench.agent.frameworks import FrameworkFactory

    _current_framework = FrameworkFactory.create(framework, settings, model_config)
    return _current_framework.build_graph()


def get_graph(framework: str = "plan_and_execute") -> CompiledStateGraph:
    """
    Get the compiled graph instance.

    Args:
        framework: Framework type to use if not already initialized

    Returns:
        Compiled LangGraph instance
    """
    global _current_framework

    if _current_framework is None:
        return build_graph(framework)

    return _current_framework.build_graph()


def get_current_framework():
    """Get the current framework instance."""
    return _current_framework


def prepare_initial_state(
    query: str,
    context: str | None = None,
    framework: str = "plan_and_execute",
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Prepare initial state for graph execution.

    Args:
        query: User query string
        context: Optional context information
        framework: Framework type
        **kwargs: Additional state fields

    Returns:
        Initial state dictionary
    """
    global _current_framework

    if _current_framework is None:
        build_graph(framework)

    return _current_framework.prepare_initial_state(query, context, **kwargs)


def extract_result(final_state: dict[str, Any]) -> dict[str, Any]:
    """
    Extract result from final state.

    Args:
        final_state: Final state after graph execution

    Returns:
        Result dictionary
    """
    global _current_framework

    if _current_framework is None:
        # Fallback to basic extraction
        return {
            "plan_result": final_state.get("plan_result", ""),
        }

    return _current_framework.extract_result(final_state)
