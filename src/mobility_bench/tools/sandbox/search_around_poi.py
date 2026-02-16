"""Search around POI sandbox tool.

Provides mock implementation of nearby POI search using cached data.
"""

import json
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from mobility_bench.tools.base import ToolResult
from mobility_bench.tools.common import ValidationError, validate_coordinate, validate_radius
from mobility_bench.tools.decorators import log_io, with_state
from mobility_bench.tools.sandbox.utils import get_sandbox_data_dir

logger = logging.getLogger(__name__)

# Load sandbox data
SANDBOX_PATH = get_sandbox_data_dir() / "search_around_poi_sandbox.json"

if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        POI_SANDBOX = json.load(f)
    logger.info(f"Loaded search around POI sandbox data: {len(POI_SANDBOX)} locations")
else:
    POI_SANDBOX = {}
    logger.warning(f"Search around POI sandbox file not found: {SANDBOX_PATH}")


@tool
@log_io
@with_state
def search_around_poi(
    location: Annotated[
        str, "Center point coordinate, format 'longitude,latitude', e.g. '116.481499,39.990755'"
    ],
    keywords: Annotated[str | None, "Search keywords, optional, e.g. gas station, restaurant"] = None,
    radius: Annotated[int, "Search radius in meters, default 10000"] = 10000,
) -> dict:
    """Search for nearby POI information based on center point coordinates."""
    try:
        validate_coordinate(location, "center coordinate")
        validate_radius(radius, min_radius=1, max_radius=50000)

        # Look up exact match location in sandbox
        location_data = POI_SANDBOX.get(location)
        if not location_data:
            return ToolResult.failed(f"No POI data for coordinate '{location}' in sandbox").to_dict()

        # If keywords provided, try matching; otherwise return all categories
        matched_pois = []
        if keywords:
            keywords_clean = keywords.strip()
            if keywords_clean in location_data:
                matched_pois = location_data[keywords_clean]
            else:
                # Fuzzy match: check if POI name contains keyword
                for category_pois in location_data.values():
                    for poi in category_pois:
                        if keywords_clean in poi.get("name", ""):
                            matched_pois.append(poi)
        else:
            for category_pois in location_data.values():
                matched_pois.extend(category_pois)

        # Deduplicate by (name, location)
        seen = set()
        unique_pois = []
        for poi in matched_pois:
            key = (poi.get("name", ""), poi.get("location", ""))
            if key not in seen:
                seen.add(key)
                unique_pois.append(poi)

        if not unique_pois:
            return ToolResult.failed(
                f"No POIs matching '{keywords or 'any'}' found near '{location}' in sandbox"
            ).to_dict()

        return ToolResult.success(unique_pois).to_dict()

    except ValidationError as e:
        logger.error(f"Search around POI input validation failed: {e}")
        return ToolResult.failed(f"Input parameter error: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"Search around POI tool error: {e}", exc_info=True)
        return ToolResult.failed(f"Internal error: {str(e)}").to_dict()
