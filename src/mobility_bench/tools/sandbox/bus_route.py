"""公交路线沙盒工具。"""

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

# === 加载公交路线沙盒数据 ===
SANDBOX_PATH = get_sandbox_data_dir() / "bus_route_mock.json"

if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        BUS_ROUTE_SANDBOX = json.load(f)
    logger.info(f"成功加载公交路线沙盒数据: {len(BUS_ROUTE_SANDBOX)} 个 destination")
else:
    BUS_ROUTE_SANDBOX = {}
    logger.warning(f"公交路线沙盒文件未找到: {SANDBOX_PATH}")


@tool
@log_io
def bus_route(
    origin: Annotated[str, "起点坐标，格式为 '经度,纬度'，例如 '116.481499,39.990755'"],
    destination: Annotated[str, "终点坐标，格式为 '经度,纬度'，例如 '116.465342,39.923423'"],
    strategy: Annotated[
        str,
        "路线策略，只能返回一个数字，默认为0，可选值：0-推荐模式，1-票价最低，2-换乘次数少，3-步行少，4-舒适（乘坐空调车），5-不坐地铁，7-地铁优先，8-时间短",
    ] = "0",
) -> dict:
    """根据起终点坐标检索符合条件的公共交通路线规划方案，支持跨城的火车、客车、飞机等方案。"""
    try:
        # 输入验证
        origin = format_decimal_places(origin)
        destination = format_decimal_places(destination)
        validate_coordinate(origin, "起点坐标")
        validate_coordinate(destination, "终点坐标")

        # 校验 strategy 合法性
        valid_strategies = {"0", "1", "2", "3", "4", "5", "7", "8"}
        if strategy not in valid_strategies:
            raise ValidationError(f"无效的路线策略: {strategy}，可选值: {', '.join(valid_strategies)}")

        # 按 JSON 结构查找: destination → origin
        route_data, meta = match_route_str(BUS_ROUTE_SANDBOX, origin, destination)

        if not route_data:
            return ToolResult.failed(f"不支持从 '{origin}' 到 '{destination}' 的公交路线查询").to_dict()

        # 检查 mock 数据状态
        if route_data.get("status") != "SUCCESS":
            error_msg = route_data.get("data", {}).get("info", "公交路线查询失败")
            return ToolResult.failed(error_msg, route_data).to_dict()

        raw_result = route_data.get("data", {})
        if raw_result.get("status") != "1":
            error_msg = raw_result.get("info", "公交路线规划失败")
            return ToolResult.failed(error_msg, raw_result).to_dict()

        # 返回结果
        return ToolResult.success(raw_result).to_dict()

    except ValidationError as e:
        logger.error(f"公交路线输入验证失败: {e}")
        return ToolResult.failed(f"输入参数错误: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"公交路线工具执行异常: {e}", exc_info=True)
        return ToolResult.failed(f"内部错误: {str(e)}").to_dict()
