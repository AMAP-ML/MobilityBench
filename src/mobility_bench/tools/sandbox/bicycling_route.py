"""骑行路线沙盒工具。"""

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

# === 加载本地骑行路线缓存（值为已格式化的字符串）===
MOCK_BICYCLING_ROUTE_PATH = get_sandbox_data_dir() / "bicycling_route_handle.json"

if MOCK_BICYCLING_ROUTE_PATH.exists():
    with open(MOCK_BICYCLING_ROUTE_PATH, "r", encoding="utf-8") as f:
        BICYCLING_ROUTE_CACHE = json.load(f)
    logger.info(f"成功加载骑行路线缓存: {len(BICYCLING_ROUTE_CACHE)} 个 destination")
else:
    BICYCLING_ROUTE_CACHE = {}
    logger.warning(f"骑行路线缓存文件未找到: {MOCK_BICYCLING_ROUTE_PATH}")


@tool
@log_io
def bicycling_route(
    origin: Annotated[str, "起点坐标，格式为 '经度,纬度'，例如 '116.481499,39.990755'"],
    destination: Annotated[str, "终点坐标，格式为 '经度,纬度'，例如 '116.465342,39.923423'"],
) -> dict:
    """根据起终点坐标检索符合条件的骑自行车路线规划方案"""
    try:
        origin = format_decimal_places(origin)
        destination = format_decimal_places(destination)

        # 输入验证
        validate_coordinate(origin, "起点坐标")
        validate_coordinate(destination, "终点坐标")

        # 从缓存中查找结果（值应为已格式化的字符串）
        formatted_result, meta = match_route_str(BICYCLING_ROUTE_CACHE, origin, destination)

        if formatted_result is not None:
            # 直接返回缓存中的结果（已是 format_bicycling_route 的输出）
            return ToolResult.success(formatted_result).to_dict()
        else:
            error_msg = "骑行路线未缓存"
            logger.debug(f"[BICYCLING] 缓存未命中: origin={origin}, destination={destination}")
            return ToolResult.failed(error_msg).to_dict()

    except ValidationError as e:
        logger.error(f"骑行路线输入验证失败: {e}")
        return ToolResult.failed(f"输入参数错误: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"骑行路线工具执行异常: {e}", exc_info=True)
        raise
