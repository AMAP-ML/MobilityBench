"""Bus route sandbox tool.

Provides mock implementation of public transit route planning using cached data.
"""

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

# Load bus route sandbox data
SANDBOX_PATH = get_sandbox_data_dir() / "bus_route_mock.json"

if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        BUS_ROUTE_SANDBOX = json.load(f)
    logger.info(f"Loaded bus route sandbox data: {len(BUS_ROUTE_SANDBOX)} destinations")
else:
    BUS_ROUTE_SANDBOX = {}
    logger.warning(f"Bus route sandbox file not found: {SANDBOX_PATH}")


@tool
@log_io
def bus_route(
    origin: Annotated[str, "Origin coordinate, format 'longitude,latitude', e.g. '116.481499,39.990755'"],
    destination: Annotated[str, "Destination coordinate, format 'longitude,latitude', e.g. '116.465342,39.923423'"],
    strategy: Annotated[
        str,
        "Route strategy, single digit only, default 0. Options: 0-recommended, 1-lowest fare, 2-fewer transfers, 3-less walking, 4-comfortable (air-conditioned), 5-no subway, 7-subway preferred, 8-shortest time",
    ] = "0",
) -> dict:
    """Plan public transit route based on origin and destination coordinates. Supports cross-city train, bus, and flight options."""
    try:
        # Input validation
        origin = format_decimal_places(origin)
        destination = format_decimal_places(destination)
        validate_coordinate(origin, "origin coordinate")
        validate_coordinate(destination, "destination coordinate")

        # Validate strategy
        valid_strategies = {"0", "1", "2", "3", "4", "5", "7", "8"}
        if strategy not in valid_strategies:
            raise ValidationError(f"Invalid route strategy: {strategy}, valid options: {', '.join(valid_strategies)}")

        # Search by JSON structure: destination -> origin
        route_data, meta = match_route_str(BUS_ROUTE_SANDBOX, origin, destination)

        if not route_data:
            return ToolResult.failed(f"Bus route from '{origin}' to '{destination}' not supported").to_dict()

        # Check mock data status
        if route_data.get("status") != "SUCCESS":
            error_msg = route_data.get("data", {}).get("info", "Bus route query failed")
            return ToolResult.failed(error_msg, route_data).to_dict()

        raw_result = route_data.get("data", {})
        if raw_result.get("status") != "1":
            error_msg = raw_result.get("info", "Bus route planning failed")
            return ToolResult.failed(error_msg, raw_result).to_dict()

        # Return result
        return ToolResult.success(raw_result).to_dict()

    except ValidationError as e:
        logger.error(f"Bus route input validation failed: {e}")
        return ToolResult.failed(f"Input parameter error: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"Bus route tool execution error: {e}", exc_info=True)
        return ToolResult.failed(f"Internal error: {str(e)}").to_dict()


if __name__ == "__main__":
    result = bus_route.func(
        origin="126.56421,45.870083",
        destination="126.587039,45.700398"
    )
    print(result)
