"""
Base framework class for agent systems.

This module defines the abstract base class that all agent frameworks must implement.
"""

from abc import ABC, abstractmethod
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from mobility_bench.config.settings import ModelConfig, Settings


class BaseFramework(ABC):
    """
    Abstract base class for agent frameworks.

    All frameworks (Plan-and-Execute, ReAct, etc.) must implement this interface
    to ensure consistent integration with the runner system.
    """

    def __init__(self, settings: Settings | None = None, model_config: ModelConfig | None = None):
        """
        Initialize the framework.

        Args:
            settings: Global settings object
            model_config: Specific model configuration to use
        """
        self.settings = settings or Settings.get_instance()
        self.model_config = model_config

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the framework name."""
        pass

    @abstractmethod
    def build_graph(self) -> CompiledStateGraph:
        """
        Build and return the compiled LangGraph.

        Returns:
            CompiledStateGraph instance ready for execution
        """
        pass

    @abstractmethod
    def prepare_initial_state(self, query: str, context: str | None = None, **kwargs) -> dict[str, Any]:
        """
        Prepare the initial state for graph execution.

        Args:
            query: User query string
            context: Optional context information
            **kwargs: Additional state fields

        Returns:
            Initial state dictionary
        """
        pass

    @abstractmethod
    def extract_result(self, final_state: dict[str, Any]) -> dict[str, Any]:
        """
        Extract result from the final state.

        Args:
            final_state: Final state after graph execution

        Returns:
            Result dictionary with standardized fields
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"
