"""Reverse geocoding sandbox tool.

Provides mock implementation of reverse geocoding using cached data.
"""

import json
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from mobility_bench.tools.base import ToolResult
from mobility_bench.tools.common import ValidationError
from mobility_bench.tools.decorators import log_io, with_state
from mobility_bench.tools.sandbox.utils import get_sandbox_data_dir

logger = logging.getLogger(__name__)

# Load sandbox data: {"lat,lon": "address"}
SANDBOX_PATH = get_sandbox_data_dir() / "reverse_geocoding_sandbox.json"

if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        SANDBOX_DATA = json.load(f)
    logger.info(f"Loaded reverse geocoding sandbox data: {len(SANDBOX_DATA)} entries")
else:
    SANDBOX_DATA = {}
    logger.warning(f"Reverse geocoding sandbox file not found: {SANDBOX_PATH}")


@tool
@log_io
@with_state
def reverse_geocoding(
    longitude: Annotated[str, "Longitude"],
    latitude: Annotated[str, "Latitude"],
    radius: Annotated[int, "Search radius in meters, default 1000"] = 1000,
) -> dict:
    """Look up detailed address information based on longitude and latitude coordinates via reverse geocoding."""
    try:
        lon_val = float(longitude)
        lat_val = float(latitude)
        if not (-180 <= lon_val <= 180):
            raise ValidationError(f"Longitude should be in [-180,180], got: {lon_val}")
        if not (-90 <= lat_val <= 90):
            raise ValidationError(f"Latitude should be in [-90,90], got: {lat_val}")
        if not (1 <= radius <= 50000):
            raise ValidationError(f"Radius should be in [1,50000] meters, got: {radius}")

        # Key format: "latitude,longitude"
        key = f"{latitude},{longitude}"
        if key in SANDBOX_DATA:
            address = SANDBOX_DATA[key]
            if not address or not isinstance(address, str):
                return ToolResult.failed(f"Invalid address data (key='{key}')").to_dict()
            return ToolResult.success({"address": address}).to_dict()
        else:
            return ToolResult.failed(
                f"No address data found for coordinate ({longitude}, {latitude}) in sandbox"
            ).to_dict()

    except ValidationError as e:
        return ToolResult.failed(f"Input parameter error: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"Reverse geocoding error: {e}", exc_info=True)
        return ToolResult.failed(f"Internal error: {str(e)}").to_dict()
