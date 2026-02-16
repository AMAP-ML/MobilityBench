"""Tool base classes and decorators."""

import functools
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

logger = logging.getLogger(__name__)


class ToolStatus(IntEnum):
    """Tool execution status."""

    SUCCESS = 0
    FAILED = 1


@dataclass
class ToolResult:
    """Tool execution result."""

    status: ToolStatus
    data: dict[str, Any]
    error: str | None = None

    @classmethod
    def success(cls, data: dict) -> "ToolResult":
        """Create success result."""
        return cls(status=ToolStatus.SUCCESS, data=data, error=None)

    @classmethod
    def failed(cls, error: str, data: dict | None = None) -> "ToolResult":
        """Create failed result."""
        return cls(status=ToolStatus.FAILED, data=data or {}, error=error)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": int(self.status),
            "data": self.data,
            "error": self.error,
        }

    @property
    def is_success(self) -> bool:
        return self.status == ToolStatus.SUCCESS


class BaseTool:
    """Tool base class."""

    name: str = ""
    description: str = ""
    mode: str = "sandbox"  # sandbox or live

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def invoke(self, **kwargs) -> ToolResult:
        """Synchronous tool invocation."""
        raise NotImplementedError

    async def ainvoke(self, **kwargs) -> ToolResult:
        """Asynchronous tool invocation."""
        return self.invoke(**kwargs)

    def validate_args(self, **kwargs) -> str | None:
        """Validate arguments, return error message or None."""
        return None

    def __call__(self, **kwargs) -> ToolResult:
        return self.invoke(**kwargs)


def log_io(func: Callable) -> Callable:
    """Decorator for logging tool input/output."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tool_name = func.__name__

        # Log input (limit length)
        args_str = str(kwargs)[:200]
        logger.debug(f"[{tool_name}] Input: {args_str}")

        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start_time

            # Log output
            result_str = str(result)[:200]
            logger.debug(f"[{tool_name}] Output: {result_str} (elapsed: {elapsed:.2f}s)")

            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[{tool_name}] Error: {e} (elapsed: {elapsed:.2f}s)")
            raise

    return wrapper


def validate_coordinate(coord_str: str, coord_name: str = "coordinate") -> tuple[float, float]:
    """Validate coordinate format.

    Args:
        coord_str: Coordinate string, format "longitude,latitude"
        coord_name: Coordinate name (for error message)

    Returns:
        (longitude, latitude) tuple

    Raises:
        ValueError: Format error
    """
    if not coord_str or not isinstance(coord_str, str):
        raise ValueError(f"{coord_name} cannot be empty")

    parts = coord_str.split(",")
    if len(parts) != 2:
        raise ValueError(f"{coord_name} format error, should be 'longitude,latitude', e.g. '116.481499,39.990755'")

    try:
        lon, lat = float(parts[0].strip()), float(parts[1].strip())
    except ValueError:
        raise ValueError(f"{coord_name} contains non-numeric characters")

    if not (-180 <= lon <= 180):
        raise ValueError(f"{coord_name} longitude out of range [-180, 180]")
    if not (-90 <= lat <= 90):
        raise ValueError(f"{coord_name} latitude out of range [-90, 90]")

    return lon, lat


def format_decimal_places(coord_str: str, places: int = 6) -> str:
    """Format coordinate precision.

    Args:
        coord_str: Coordinate string
        places: Decimal places

    Returns:
        Formatted coordinate string
    """
    try:
        lon, lat = validate_coordinate(coord_str)
        return f"{lon:.{places}f},{lat:.{places}f}"
    except ValueError:
        return coord_str
