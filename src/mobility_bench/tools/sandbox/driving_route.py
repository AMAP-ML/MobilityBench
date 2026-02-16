"""Driving route sandbox tool."""

import json
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from mobility_bench.tools.base import ToolResult
from mobility_bench.tools.common import ValidationError, validate_coordinate
from mobility_bench.tools.decorators import log_io
from mobility_bench.tools.sandbox.utils import format_decimal_places, get_sandbox_data_dir, match_route_str

logger = logging.getLogger(__name__)

# Load sandbox data
SANDBOX_PATH = get_sandbox_data_dir() / "driving_route_handle.json"
ROUTE_SANDBOX = {}
if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        ROUTE_SANDBOX = json.load(f)
else:
    logger.warning(f"Sandbox data not found: {SANDBOX_PATH}")


def _strategy_to_key(strategy_list):
    if not strategy_list:
        return "default"
    return "+".join(sorted(strategy_list))


def _waypoints_to_key(waypoints_list):
    if not waypoints_list:
        return "default"
    return ";".join(waypoints_list)


@tool
@log_io
def driving_route(
    origin: Annotated[str, "Origin coordinate, format 'longitude,latitude', e.g. '116.481499,39.990755'"],
    destination: Annotated[str, "Destination coordinate, format 'longitude,latitude', e.g. '116.465342,39.923423'"],
    strategy: Annotated[
        list[str],
        "Driving route strategy, options: 'avoid_congestion', 'highway_priority', 'no_highway', 'less_toll', 'main_road', 'fastest'. Max 2 items."
    ] = [],
    waypoints: Annotated[list[str], "Waypoint coordinates, format longitude,latitude. Max 5 waypoints."] = [],
) -> dict:
    """Plan driving route based on origin and destination coordinates, supports waypoints."""
    try:
        # Input validation
        origin = format_decimal_places(origin)
        destination = format_decimal_places(destination)
        validate_coordinate(origin, "origin")
        validate_coordinate(destination, "destination")

        if len(strategy) > 2:
            raise ValidationError("Strategy count cannot exceed 2")
        if len(waypoints) > 5:
            raise ValidationError("Waypoint count cannot exceed 5")

        # Build lookup keys
        strategy_key = _strategy_to_key(strategy)
        waypoints_key = _waypoints_to_key(waypoints)

        # Look up in sandbox data
        origin_data, meta = match_route_str(ROUTE_SANDBOX, origin, destination)
        if not origin_data:
            return ToolResult.failed(f"Route from '{origin}' to '{destination}' not supported").to_dict()

        strategy_data = origin_data.get(strategy_key)
        if not strategy_data:
            # Fallback to default strategy
            strategy_data = origin_data.get("default")
            if not strategy_data:
                return ToolResult.failed(f"Strategy {strategy} not supported").to_dict()

        route_data = strategy_data.get(waypoints_key)
        if not route_data:
            # Fallback to default waypoints
            route_data = strategy_data.get("default")
            if not route_data:
                return ToolResult.failed(f"Waypoints {waypoints} not supported").to_dict()

        # Return result
        if route_data.get("status") == "1":
            return ToolResult.success(route_data).to_dict()
        else:
            error_msg = route_data.get("info", "Route planning failed")
            return ToolResult.failed(error_msg, route_data).to_dict()

    except ValidationError as e:
        logger.error(f"Validation failed: {e}")
        return ToolResult.failed(f"Input parameter error: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"Driving route error: {e}", exc_info=True)
        return ToolResult.failed(f"Internal error: {str(e)}").to_dict()
