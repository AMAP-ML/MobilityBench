"""Evaluation metric registry."""

import logging
from typing import Optional

from mobility_bench.evaluation.base import BaseMetric

logger = logging.getLogger(__name__)


class MetricRegistry:
    """Evaluation metric registry."""

    _instance: Optional["MetricRegistry"] = None
    _metrics: dict[str, type[BaseMetric]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._metrics = {}
        return cls._instance

    @classmethod
    def register(cls, name: str, metric_class: type[BaseMetric]):
        """Register evaluation metric.

        Args:
            name: Metric name
            metric_class: Metric class
        """
        instance = cls()
        instance._metrics[name] = metric_class
        logger.debug(f"Registered evaluation metric: {name}")

    @classmethod
    def get(cls, name: str, config: dict | None = None) -> BaseMetric | None:
        """Get evaluation metric instance.

        Args:
            name: Metric name
            config: Configuration

        Returns:
            Metric instance or None
        """
        instance = cls()
        metric_class = instance._metrics.get(name)

        if metric_class is None:
            return None

        return metric_class(config=config)

    @classmethod
    def list_names(cls) -> list[str]:
        """List all metric names."""
        instance = cls()
        return list(instance._metrics.keys())

    @classmethod
    def get_all(cls, config: dict | None = None) -> list[BaseMetric]:
        """Get all metric instances."""
        instance = cls()
        return [
            metric_class(config=config)
            for metric_class in instance._metrics.values()
        ]

    @classmethod
    def clear(cls):
        """Clear registry."""
        instance = cls()
        instance._metrics.clear()

    @classmethod
    def load_default_metrics(cls):
        """Load default evaluation metrics."""
        from mobility_bench.evaluation.metrics.answer import AnswerMetric
        from mobility_bench.evaluation.metrics.efficiency import EfficiencyMetric
        from mobility_bench.evaluation.metrics.instruction import InstructionMetric
        from mobility_bench.evaluation.metrics.planning import PlanningMetric
        from mobility_bench.evaluation.metrics.tool_call import ToolCallMetric

        cls.register("tool", ToolCallMetric)
        cls.register("instruction", InstructionMetric)
        cls.register("planning", PlanningMetric)
        cls.register("answer", AnswerMetric)
        cls.register("efficiency", EfficiencyMetric)

        logger.info("Loaded default evaluation metrics")


def register_metric(name: str):
    """Evaluation metric registration decorator.

    Usage:
        @register_metric("my_metric")
        class MyMetric(BaseMetric):
            ...
    """

    def decorator(cls):
        MetricRegistry.register(name, cls)
        return cls

    return decorator
