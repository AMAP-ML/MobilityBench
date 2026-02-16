"""Tool decorators."""

import functools
import logging
import time
from collections.abc import Callable
from typing import Any

from mobility_bench.tools.base import ToolResult

logger = logging.getLogger(__name__)


def log_io(func: Callable) -> Callable:
    """
    A decorator that logs the input parameters and output of a tool function.

    Args:
        func: The tool function to be decorated

    Returns:
        The wrapped function with input/output logging
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        func_name = func.__name__
        params = ", ".join(
            [*(str(arg) for arg in args), *(f"{k}={v}" for k, v in kwargs.items())]
        )
        # Limit parameter length to avoid long output
        params_preview = params[:200] + "..." if len(params) > 200 else params
        logger.debug(f"Tool {func_name} called with parameters: {params_preview}")

        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time

        # Log the output (limit length)
        result_str = str(result)
        result_preview = result_str[:200] + "..." if len(result_str) > 200 else result_str
        logger.debug(f"Tool {func_name} returned: {result_preview} (elapsed: {elapsed:.2f}s)")

        return result

    return wrapper


def with_state(func: Callable) -> Callable:
    """
    Decorator that provides state context access to tool functions.

    This is a simplified version that just passes through without state management.
    For full state management, integrate with the agent's state system.

    Usage:
        @tool
        @log_io
        @with_state
        def my_tool(...):
            return ToolResult.success(data).to_dict()
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.time()
        tool_name = func.__name__

        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time
            logger.debug(f"Tool {tool_name} completed in {elapsed:.2f}s")
            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Tool {tool_name} failed after {elapsed:.2f}s: {e}")
            return ToolResult.failed(str(e)).to_dict()

    return wrapper
