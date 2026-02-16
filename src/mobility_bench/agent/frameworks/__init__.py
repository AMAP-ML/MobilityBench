"""
Agent frameworks module.

This module provides the framework factory and base classes for different
agent architectures (Plan-and-Execute, ReAct, etc.).
"""

from mobility_bench.agent.frameworks.base import BaseFramework
from mobility_bench.agent.frameworks.plan_and_execute import PlanAndExecuteFramework
from mobility_bench.agent.frameworks.react import ReactFramework
from mobility_bench.config.settings import ModelConfig, Settings


class FrameworkFactory:
    """
    Factory for creating agent frameworks.

    Supports registration of custom frameworks and provides a unified
    interface for framework instantiation.
    """

    _frameworks: dict[str, type[BaseFramework]] = {
        "plan_and_execute": PlanAndExecuteFramework,
        "react": ReactFramework,
    }

    @classmethod
    def create(
        cls,
        framework_type: str,
        settings: Settings | None = None,
        model_config: ModelConfig | None = None,
    ) -> BaseFramework:
        """
        Create a framework instance.

        Args:
            framework_type: Framework type name (e.g., "plan_and_execute", "react")
            settings: Global settings object
            model_config: Specific model configuration

        Returns:
            Framework instance

        Raises:
            ValueError: If framework type is unknown
        """
        framework_class = cls._frameworks.get(framework_type)
        if framework_class is None:
            available = ", ".join(cls._frameworks.keys())
            raise ValueError(
                f"Unknown framework type: {framework_type}. Available: {available}"
            )

        return framework_class(settings, model_config)

    @classmethod
    def register(cls, name: str, framework_class: type[BaseFramework]) -> None:
        """
        Register a custom framework.

        Args:
            name: Framework name for lookup
            framework_class: Framework class (must inherit from BaseFramework)
        """
        if not issubclass(framework_class, BaseFramework):
            raise TypeError(f"Framework class must inherit from BaseFramework")

        cls._frameworks[name] = framework_class

    @classmethod
    def list_frameworks(cls) -> list[str]:
        """Return list of available framework names."""
        return list(cls._frameworks.keys())

    @classmethod
    def get_framework_class(cls, name: str) -> type[BaseFramework] | None:
        """Get framework class by name."""
        return cls._frameworks.get(name)


__all__ = [
    "BaseFramework",
    "FrameworkFactory",
    "PlanAndExecuteFramework",
    "ReactFramework",
]
