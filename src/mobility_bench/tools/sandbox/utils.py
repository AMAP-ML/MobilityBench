"""沙盒工具公共函数。"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 默认: <项目根目录>/data/sandbox
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_DATA_DIR = _PROJECT_ROOT / "data" / "sandbox"


def get_sandbox_data_dir() -> Path:
    """返回沙盒数据目录路径。

    从 Settings 的 agent.sandbox_data_dir 配置读取。
    相对路径基于项目根目录解析。
    默认: <project_root>/data/sandbox
    """
    try:
        from mobility_bench.config.settings import Settings
        settings = Settings.get_instance()
        configured = settings.agent.sandbox_data_dir
        if configured:
            p = Path(configured)
            if not p.is_absolute():
                p = _PROJECT_ROOT / p
            return p
    except Exception:
        pass
    return _DEFAULT_DATA_DIR


def match_route_str(route_data: dict, origin: str, destination: str) -> tuple[dict | None, dict]:
    """
    Match route data by origin and destination coordinates.

    Args:
        route_data: Nested dictionary with route data
        origin: Origin coordinate string
        destination: Destination coordinate string

    Returns:
        Tuple of (matched_data, metadata) or (None, {}) if not found
    """
    # Try exact match first
    dest_data = route_data.get(destination)
    if dest_data:
        origin_data = dest_data.get(origin)
        if origin_data:
            return origin_data, {"match_type": "exact"}

    # Try fuzzy match by rounding coordinates
    try:
        dest_lon, dest_lat = map(float, destination.split(","))
        orig_lon, orig_lat = map(float, origin.split(","))

        # Round to 4 decimal places for fuzzy match
        dest_key_fuzzy = f"{dest_lon:.4f},{dest_lat:.4f}"
        orig_key_fuzzy = f"{orig_lon:.4f},{orig_lat:.4f}"

        for dest_key, dest_routes in route_data.items():
            try:
                d_lon, d_lat = map(float, dest_key.split(","))
                if abs(d_lon - dest_lon) < 0.001 and abs(d_lat - dest_lat) < 0.001:
                    for orig_key, orig_routes in dest_routes.items():
                        try:
                            o_lon, o_lat = map(float, orig_key.split(","))
                            if abs(o_lon - orig_lon) < 0.001 and abs(o_lat - orig_lat) < 0.001:
                                return orig_routes, {"match_type": "fuzzy"}
                        except (ValueError, AttributeError):
                            continue
            except (ValueError, AttributeError):
                continue

    except (ValueError, AttributeError) as e:
        logger.debug(f"Fuzzy match failed: {e}")

    return None, {}


def format_decimal_places(coord_str: str, places: int = 6) -> str:
    """
    Format coordinate string to specified decimal places.

    Args:
        coord_str: Coordinate string "longitude,latitude"
        places: Number of decimal places

    Returns:
        Formatted coordinate string
    """
    try:
        parts = coord_str.split(",")
        if len(parts) != 2:
            return coord_str

        lon, lat = float(parts[0].strip()), float(parts[1].strip())
        return f"{lon:.{places}f},{lat:.{places}f}"
    except (ValueError, AttributeError):
        return coord_str
