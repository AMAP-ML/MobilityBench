"""步行路线沙盒工具。"""

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

# === 加载本地缓存的步行路线数据 ===
WALKING_ROUTE_CACHE_PATH = get_sandbox_data_dir() / "walking_route_handle.json"

# 全局加载一次（避免每次调用都读文件）
if WALKING_ROUTE_CACHE_PATH.exists():
    with open(WALKING_ROUTE_CACHE_PATH, "r", encoding="utf-8") as f:
        WALKING_ROUTE_CACHE = json.load(f)
    logger.info(f"成功加载步行路线缓存: {len(WALKING_ROUTE_CACHE)} 个 destination")
else:
    WALKING_ROUTE_CACHE = {}
    logger.warning(f"步行路线缓存文件未找到: {WALKING_ROUTE_CACHE_PATH}")


def walking_route_api(
    origin: Annotated[str, "起点坐标，格式为 '经度,纬度'，例如 '116.481499,39.990755'"],
    destination: Annotated[str, "终点坐标，格式为 '经度,纬度'，例如 '116.465342,39.923423'"],
) -> dict:
    """从本地 JSON 缓存中获取步行路线结果（替代 API 调用）"""
    logger.debug(f"从缓存查询步行路线: origin={origin}, destination={destination}")

    # 从缓存中模糊匹配查找
    result, meta = match_route_str(WALKING_ROUTE_CACHE, origin, destination)
    if result is None:
        logger.debug("步行路线缓存未命中")
        return {
            "status": "0",
            "info": "步行路线未缓存",
            "infocode": "CACHE_MISS",
            "route": {}
        }

    logger.debug("缓存命中，返回缓存结果")
    return result


@tool
@log_io
def walking_route(
    origin: Annotated[str, "起点坐标，格式为 '经度,纬度'，例如 '116.481499,39.990755'"],
    destination: Annotated[str, "终点坐标，格式为 '经度,纬度'，例如 '116.465342,39.923423'"],
) -> dict:
    """根据起终点坐标检索符合条件的步行路线规划方案"""
    try:
        origin = format_decimal_places(origin)
        destination = format_decimal_places(destination)

        # 输入验证
        validate_coordinate(origin, "起点坐标")
        validate_coordinate(destination, "终点坐标")

        result = walking_route_api(origin, destination)

        if result.get("status") == "1":
            return ToolResult.success(result).to_dict()
        else:
            error_msg = result.get("info", "步行路线规划失败")
            return ToolResult.failed(error_msg, result).to_dict()

    except ValidationError as e:
        logger.error(f"步行路线输入验证失败: {e}")
        return ToolResult.failed(f"输入参数错误: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"步行路线工具执行异常: {e}", exc_info=True)
        raise
