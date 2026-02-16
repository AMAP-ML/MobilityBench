"""Weather query sandbox tool.

Provides mock implementation of weather query using cached data.
"""

import json
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from mobility_bench.tools.base import ToolResult
from mobility_bench.tools.common import ValidationError, validate_city
from mobility_bench.tools.decorators import log_io, with_state
from mobility_bench.tools.sandbox.utils import get_sandbox_data_dir

logger = logging.getLogger(__name__)


def normalize_location(name: str) -> str:
    """Remove common administrative suffixes, return core location name."""
    if not name or not isinstance(name, str):
        return name
    suffixes = ["Province", "City", "County", "District", "Prefecture", "SAR",
                "省", "市", "县", "区", "自治州", "特别行政区"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name


# Load sandbox data and build normalized mapping
SANDBOX_PATH = get_sandbox_data_dir() / "weather_sandbox.json"

if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        RAW_SANDBOX = json.load(f)
    logger.info(f"Loaded weather sandbox data: {len(RAW_SANDBOX)} cities")
else:
    RAW_SANDBOX = {}
    logger.warning(f"Weather sandbox file not found: {SANDBOX_PATH}")

# Build {normalized_key: original_key} mapping
NORMALIZED_TO_ORIGINAL = {}
for original_key in RAW_SANDBOX:
    norm_key = normalize_location(original_key)
    # If conflict occurs (e.g., "Shandong" and "Shandong Province" both become "Shandong"),
    # the latter will overwrite the former
    NORMALIZED_TO_ORIGINAL[norm_key] = original_key


@tool
@log_io
@with_state
def weather_query(
    city: Annotated[str, "City name, e.g., 'Beijing', 'Shanghai', 'Guangzhou'"],
    need_forecast: Annotated[
        bool, "Whether to include future weather forecast. True for forecast, False for current weather only"
    ] = False,
) -> dict:
    """Query weather information for a specified location."""
    try:
        validated_city = validate_city(city)
        if not validated_city:
            return ToolResult.failed("City name cannot be empty, please provide a valid city name").to_dict()

        # Normalize user input
        norm_input = normalize_location(validated_city)

        # Search in normalized mapping
        original_key = NORMALIZED_TO_ORIGINAL.get(norm_input)
        if not original_key:
            return ToolResult.failed(f"Weather query for '{validated_city}' is not supported").to_dict()

        city_data = RAW_SANDBOX[original_key]
        forecast_key = str(need_forecast)  # JSON uses "True"/"False" as keys

        if forecast_key in city_data:
            weather_desc = city_data[forecast_key]["weather_description"]
            return ToolResult.success({"weather_description": weather_desc}).to_dict()
        else:
            action = "weather forecast" if need_forecast else "current weather"
            return ToolResult.failed(f"No {action} data available for '{original_key}'").to_dict()

    except ValidationError as e:
        logger.error(f"Weather query input validation failed: {e}")
        return ToolResult.failed(f"Input parameter error: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"Weather query tool execution error: {e}", exc_info=True)
        return ToolResult.failed(f"Internal error: {str(e)}").to_dict()
