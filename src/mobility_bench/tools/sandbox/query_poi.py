"""POI query sandbox tool."""

import json
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from mobility_bench.tools.base import ToolResult
from mobility_bench.tools.common import ValidationError, validate_address, validate_city
from mobility_bench.tools.decorators import log_io, with_state
from mobility_bench.tools.sandbox.utils import get_sandbox_data_dir

logger = logging.getLogger(__name__)

# Load sandbox data
SANDBOX_PATH = get_sandbox_data_dir() / "nested_poi_data.json"
MOCK_POI_DATA = {}
if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        MOCK_POI_DATA = json.load(f)
else:
    logger.warning(f"Sandbox data not found: {SANDBOX_PATH}")


def _lookup_real_result(keyword: str, city: str | None) -> dict | None:
    """
    Lookup POI data by keyword and city.

    1. If keyword not found -> return None
    2. If keyword found:
       - Try exact city match
       - If match fails or no city -> return first result
    """
    if keyword not in MOCK_POI_DATA:
        return None

    city_map = MOCK_POI_DATA[keyword]

    # If city provided, try to match
    if city is not None and city != "":
        city_clean = city.rstrip("市") if city.endswith("市") else city
        for stored_city, poi_info in city_map.items():
            stored_clean = stored_city.rstrip("市") if stored_city.endswith("市") else stored_city
            if city_clean == stored_clean:
                return poi_info

    # No city or match failed -> return first result
    first_result = next(iter(city_map.values()))
    return first_result


@tool
@log_io
@with_state
def query_poi(
    keywords: Annotated[str, "Keywords to search, e.g. Tiananmen, KFC"],
    city: Annotated[str | None, "City name, optional, e.g. Beijing, Shanghai"] = None,
) -> dict:
    """Search for precise location information and coordinates based on fuzzy location input."""
    try:
        validated_keywords = validate_address(keywords)
        effective_city = city

        if effective_city:
            effective_city = validate_city(effective_city)

        # Look up result
        real_result = _lookup_real_result(validated_keywords, effective_city)

        if real_result is None:
            logger.info(f"Keyword '{validated_keywords}' not found in sandbox data")
            return ToolResult.failed(f"POI '{validated_keywords}' not found in sandbox").to_dict()

        # Build return result
        filtered_poi = {
            "location": real_result.get("location", ""),
            "name": real_result.get("name", ""),
            "address": real_result.get("address", ""),
        }

        logger.info(f"POI query success - keywords: '{validated_keywords}', city: '{effective_city}'")

        return ToolResult.success(filtered_poi).to_dict()

    except ValidationError as e:
        return ToolResult.failed(f"Input parameter error: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"POI query error: {e}", exc_info=True)
        return ToolResult.failed(f"Internal error: {str(e)}").to_dict()
