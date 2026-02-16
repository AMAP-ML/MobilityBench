"""
Graph node execution decorators.
Automatically records node execution process, error handling and state update merging.
"""

import functools
import logging
from collections.abc import Callable
from typing import Any

from langgraph.types import Command
from opentelemetry.trace import Status, StatusCode

from mobility_bench.agent.utils.telemetry import SpanKind, log_event, start_span

logger = logging.getLogger(__name__)


def record_execution(node_name: str | Callable, phase: str | None = None):
    """
    Node execution recording decorator.

    Args:
        node_name: Node name, can be string or function (for dynamic nodes)
        phase: Execution phase name

    Usage:
        @record_execution("coordinator", "coordination")
        async def coordinator_node(state, config): ...

        @record_execution(lambda state: f"worker_{state.get('task_id')}")
        async def worker_node(state, config): ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(state: dict[str, Any], config=None) -> dict[str, Any]:
            # Get node name
            if callable(node_name):
                current_node_name = node_name(state)
            else:
                current_node_name = node_name

            # Get phase name
            current_phase = phase or current_node_name

            logger.info(f"[{current_node_name.upper()}] Node execution started")

            updates: dict[str, Any] = {}
            span_attributes = {
                "graph.node": current_node_name,
                "graph.phase": current_phase,
                "graph.state_keys": list(state.keys()),
                "graph.state_size": len(state),
            }

            with start_span(
                f"graph.{current_node_name}",
                kind=SpanKind.INTERNAL,
                component="graph",
                attributes=span_attributes,
            ) as span:
                log_event(
                    "graph_node_started",
                    {
                        "node": current_node_name,
                        "phase": current_phase,
                        "state_keys": list(state.keys()),
                    },
                )

                try:
                    if not current_node_name.startswith("worker_"):
                        logger.debug(
                            f"[{current_node_name.upper()}] Entering execution phase: {current_phase}"
                        )

                    if config is not None:
                        node_result = await func(state, config)
                    else:
                        node_result = await func(state)

                    logger.info(f"[{current_node_name.upper()}] Node execution completed")

                    if isinstance(node_result, Command):
                        goto_target = node_result.goto
                        if node_result.update:
                            _merge_updates(updates, node_result.update)
                        log_event(
                            "graph_node_completed",
                            {
                                "node": current_node_name,
                                "phase": current_phase,
                                "goto": str(goto_target),
                                "update_keys": list(updates.keys()),
                            },
                        )
                        return Command(update=updates, goto=goto_target)
                    elif node_result:
                        _merge_updates(updates, node_result)
                        log_event(
                            "graph_node_completed",
                            {
                                "node": current_node_name,
                                "phase": current_phase,
                                "goto": None,
                                "update_keys": list(updates.keys()),
                            },
                        )
                        return updates

                    log_event(
                        "graph_node_completed",
                        {
                            "node": current_node_name,
                            "phase": current_phase,
                            "goto": None,
                            "update_keys": [],
                        },
                    )
                    return updates

                except Exception as e:  # pragma: no cover - defensive logging
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    error_message = f"Node {current_node_name} execution failed: {str(e)}"
                    logger.error(f"{error_message}", exc_info=True)
                    log_event(
                        "graph_node_failed",
                        {
                            "node": current_node_name,
                            "phase": current_phase,
                            "error": str(e),
                        },
                    )
                    raise

            return updates

        return wrapper

    return decorator


class ExecutionRecorder:
    """
    Simplified execution recorder - pure logging.
    """

    def __init__(self, state: dict[str, Any], node: str):
        self.node = node

    def tool_call(self, tool_name: str, args: dict[str, Any] = None):
        """Record tool call."""
        logger.info(f"[{self.node.upper()}] {tool_name}")

    def parallel_start(self, task_count: int, description: str = ""):
        """Record parallel tasks start."""
        message = f"Creating {task_count} parallel tasks"
        if description:
            message += f": {description}"
        logger.info(f"[{self.node.upper()}] {message}")


def get_execution_recorder(state: dict[str, Any], node: str) -> ExecutionRecorder:
    """Get execution recorder."""
    return ExecutionRecorder(state, node)


def _merge_updates(target: dict[str, Any], source: dict[str, Any]):
    """
    Merge state updates, handles smart merging logic for different field types.

    All fields are directly overwritten.
    """
    for key, value in source.items():
        # All fields directly overwritten
        target[key] = value
