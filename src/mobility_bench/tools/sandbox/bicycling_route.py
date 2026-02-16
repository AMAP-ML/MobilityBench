"""Bicycling route sandbox tool.

Provides mock implementation of bicycling route planning using cached data.
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

# Load bicycling route cache data
MOCK_BICYCLING_ROUTE_PATH = get_sandbox_data_dir() / "bicycling_route_handle.json"

if MOCK_BICYCLING_ROUTE_PATH.exists():
    with open(MOCK_BICYCLING_ROUTE_PATH, "r", encoding="utf-8") as f:
        BICYCLING_ROUTE_CACHE = json.load(f)
    logger.info(f"Loaded bicycling route cache: {len(BICYCLING_ROUTE_CACHE)} destinations")
else:
    BICYCLING_ROUTE_CACHE = {}
    logger.warning(f"Bicycling route cache file not found: {MOCK_BICYCLING_ROUTE_PATH}")


@tool
@log_io
def bicycling_route(
    origin: Annotated[str, "Origin coordinate, format 'longitude,latitude', e.g. '116.481499,39.990755'"],
    destination: Annotated[str, "Destination coordinate, format 'longitude,latitude', e.g. '116.465342,39.923423'"],
) -> dict:
    """Plan bicycling route based on origin and destination coordinates."""
    try:
        origin = format_decimal_places(origin)
        destination = format_decimal_places(destination)

        # Input validation
        validate_coordinate(origin, "origin coordinate")
        validate_coordinate(destination, "destination coordinate")

        # Search result from cache (value should be pre-formatted string)
        formatted_result, meta = match_route_str(BICYCLING_ROUTE_CACHE, origin, destination)

        if formatted_result is not None:
            # Return cached result directly (already formatted by format_bicycling_route)
            return ToolResult.success(formatted_result).to_dict()
        else:
            error_msg = "Bicycling route not cached"
            logger.debug(f"[BICYCLING] Cache miss: origin={origin}, destination={destination}")
            return ToolResult.failed(error_msg).to_dict()

    except ValidationError as e:
        logger.error(f"Bicycling route input validation failed: {e}")
        return ToolResult.failed(f"Input parameter error: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"Bicycling route tool execution error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    result = bicycling_route.func(
        origin="113.856808,34.528476",
        destination="113.777059,34.759055"
    )
    print(result)
