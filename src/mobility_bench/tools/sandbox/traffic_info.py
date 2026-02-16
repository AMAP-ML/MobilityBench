"""Traffic info sandbox tool.

Provides mock implementation of traffic status query using cached data.
"""

import json
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from mobility_bench.tools.base import ToolResult
from mobility_bench.tools.common import ValidationError
from mobility_bench.tools.decorators import log_io
from mobility_bench.tools.sandbox.utils import get_sandbox_data_dir

logger = logging.getLogger(__name__)

# Load sandbox data
SANDBOX_PATH = get_sandbox_data_dir() / "traffic_info_mock.json"

if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        TRAFFIC_SANDBOX = json.load(f)
    logger.info(f"Loaded traffic info sandbox data: {len(TRAFFIC_SANDBOX)} roads")
else:
    TRAFFIC_SANDBOX = {}
    logger.warning(f"Traffic info sandbox file not found: {SANDBOX_PATH}")


@tool
@log_io
def traffic_status(
    name: Annotated[str, "Road name, e.g. 'Jinggangao Expressway'"],
    city: Annotated[str, "City name, e.g. 'Beijing', 'Shanghai'"],
) -> dict:
    """Query real-time traffic status for a specified road in a city."""
    try:
        if not name or not isinstance(name, str):
            raise ValidationError("Road name cannot be empty")
        if not city or not isinstance(city, str):
            raise ValidationError("City name cannot be empty")

        name = name.strip()
        city = city.strip()

        if not name:
            raise ValidationError("Road name cannot be empty")
        if not city:
            raise ValidationError("City name cannot be empty")

        # Look up in sandbox data
        city_data = TRAFFIC_SANDBOX.get(name)
        if not city_data:
            return ToolResult.failed(f"Traffic query for road '{name}' is not supported").to_dict()

        traffic_data = city_data.get(city)
        if not traffic_data:
            return ToolResult.failed(f"Traffic query for '{name}' in '{city}' is not supported").to_dict()

        if traffic_data.get("status") == "1":
            return ToolResult.success(traffic_data).to_dict()
        else:
            error_msg = traffic_data.get("info", "Traffic query failed")
            return ToolResult.failed(error_msg, traffic_data).to_dict()

    except ValidationError as e:
        logger.error(f"Traffic info input validation failed: {e}")
        return ToolResult.failed(f"Input parameter error: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"Traffic info tool error: {e}", exc_info=True)
        return ToolResult.failed(f"Internal error: {str(e)}").to_dict()
