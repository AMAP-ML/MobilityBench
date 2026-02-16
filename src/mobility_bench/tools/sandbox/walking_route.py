"""Walking route sandbox tool.

Provides mock implementation of walking route planning using cached data.
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

# Load walking route cache data
WALKING_ROUTE_CACHE_PATH = get_sandbox_data_dir() / "walking_route_handle.json"

# Load cache once at module level
if WALKING_ROUTE_CACHE_PATH.exists():
    with open(WALKING_ROUTE_CACHE_PATH, "r", encoding="utf-8") as f:
        WALKING_ROUTE_CACHE = json.load(f)
    logger.info(f"Loaded walking route cache: {len(WALKING_ROUTE_CACHE)} destinations")
else:
    WALKING_ROUTE_CACHE = {}
    logger.warning(f"Walking route cache file not found: {WALKING_ROUTE_CACHE_PATH}")


def walking_route_api(
    origin: Annotated[str, "Origin coordinate, format 'longitude,latitude', e.g. '116.481499,39.990755'"],
    destination: Annotated[str, "Destination coordinate, format 'longitude,latitude', e.g. '116.465342,39.923423'"],
) -> dict:
    """Get walking route result from local JSON cache (replaces API call)."""
    logger.debug(f"Querying walking route from cache: origin={origin}, destination={destination}")

    # Search in cache with fuzzy matching
    result, meta = match_route_str(WALKING_ROUTE_CACHE, origin, destination)
    if result is None:
        logger.debug("Walking route not found in cache")
        return {
            "status": "0",
            "info": "Walking route not cached",
            "infocode": "CACHE_MISS",
            "route": {}
        }

    # Return cached result (simulates API response)
    logger.debug("Cache hit, returning cached result")
    return result


@tool
@log_io
def walking_route(
    origin: Annotated[str, "Origin coordinate, format 'longitude,latitude', e.g. '116.481499,39.990755'"],
    destination: Annotated[str, "Destination coordinate, format 'longitude,latitude', e.g. '116.465342,39.923423'"],
) -> dict:
    """Plan walking route based on origin and destination coordinates."""
    try:
        origin = format_decimal_places(origin)
        destination = format_decimal_places(destination)

        # Input validation
        validate_coordinate(origin, "origin coordinate")
        validate_coordinate(destination, "destination coordinate")

        result = walking_route_api(origin, destination)

        if result.get("status") == "1":
            return ToolResult.success(result).to_dict()
        else:
            error_msg = result.get("info", "Walking route planning failed")
            return ToolResult.failed(error_msg, result).to_dict()

    except ValidationError as e:
        logger.error(f"Walking route input validation failed: {e}")
        return ToolResult.failed(f"Input parameter error: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"Walking route tool execution error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    result = walking_route.func(
        origin="113.856808,34.528476",
        destination="113.777059,34.759055"
    )
    print(result)
