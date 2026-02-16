"""驾车路线沙盒工具。"""

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

# 加载四层 JSON 沙盒
SANDBOX_PATH = get_sandbox_data_dir() / "driving_route_handle.json"
ROUTE_SANDBOX = {}
if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        ROUTE_SANDBOX = json.load(f)
else:
    logger.warning(f"沙盒数据未找到: {SANDBOX_PATH}")


def _strategy_to_key(strategy_list):
    if not strategy_list:
        return "default"
    return "+".join(sorted(strategy_list))


def _waypoints_to_key(waypoints_list):
    if not waypoints_list:
        return "default"
    return ";".join(waypoints_list)


@tool
@log_io
def driving_route(
    origin: Annotated[str, "起点坐标，格式为 '经度,纬度'，例如 '116.481499,39.990755'"],
    destination: Annotated[str, "终点坐标，格式为 '经度,纬度'，例如 '116.465342,39.923423'"],
    strategy: Annotated[
        list[str],
        "驾车算路策略，可选值包括：'躲避拥堵'、'高速优先'、'不走高速'、'少收费'、'大路优先'、'速度最快'。例如：['躲避拥堵', '高速优先']。最多选择2项。"
    ] = [],
    waypoints: Annotated[list[str], "途经点坐标，格式为经度,纬度。例如：['116.473195,39.993253']。最多选择5个途经点。"] = [],
) -> dict:
    """根据起终点坐标检索符合条件的驾车路线规划方案，支持填加途径点"""
    try:
        # 输入验证
        origin = format_decimal_places(origin)
        destination = format_decimal_places(destination)
        validate_coordinate(origin, "起点坐标")
        validate_coordinate(destination, "终点坐标")

        if len(strategy) > 2:
            raise ValidationError("策略数量不能超过2个")
        if len(waypoints) > 5:
            raise ValidationError("途经点数量不能超过5个")

        # 构建查找键
        strategy_key = _strategy_to_key(strategy)
        waypoints_key = _waypoints_to_key(waypoints)

        # 按四层结构查找
        origin_data, meta = match_route_str(ROUTE_SANDBOX, origin, destination)
        if not origin_data:
            return ToolResult.failed(f"不支持从 '{origin}' 到 '{destination}' 的路线查询").to_dict()

        strategy_data = origin_data.get(strategy_key)
        if not strategy_data:
            # 尝试回退到 default 策略
            strategy_data = origin_data.get("default")
            if not strategy_data:
                return ToolResult.failed(f"不支持策略 {strategy}").to_dict()

        route_data = strategy_data.get(waypoints_key)
        if not route_data:
            # 尝试回退到 default 途经点
            route_data = strategy_data.get("default")
            if not route_data:
                return ToolResult.failed(f"不支持途经点 {waypoints}").to_dict()

        # 返回结果
        if route_data.get("status") == "1":
            return ToolResult.success(route_data).to_dict()
        else:
            error_msg = route_data.get("info", "路线规划失败")
            return ToolResult.failed(error_msg, route_data).to_dict()

    except ValidationError as e:
        logger.error(f"驾车路线输入验证失败: {e}")
        return ToolResult.failed(f"输入参数错误: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"驾车路线工具异常: {e}", exc_info=True)
        return ToolResult.failed(f"内部错误: {str(e)}").to_dict()
