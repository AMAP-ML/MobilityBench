"""交通路况沙盒工具。"""

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

# === 加载交通路况沙盒数据 ===
SANDBOX_PATH = get_sandbox_data_dir() / "traffic_info_mock.json"

if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        TRAFFIC_SANDBOX = json.load(f)
    logger.info(f"成功加载交通路况沙盒数据: {len(TRAFFIC_SANDBOX)} 条道路")
else:
    TRAFFIC_SANDBOX = {}
    logger.warning(f"交通路况沙盒文件未找到: {SANDBOX_PATH}")


@tool
@log_io
def traffic_status(
    name: Annotated[str, "道路名称，例如：'京港澳高速'、'外环'"],
    city: Annotated[str, "城市名称，例如：'北京市'、'上海市'"],
) -> dict:
    """查询指定城市某条道路的实时交通状况"""
    try:
        # 输入验证
        if not name or not isinstance(name, str):
            raise ValidationError("道路名称不能为空")
        if not city or not isinstance(city, str):
            raise ValidationError("城市名称不能为空")

        name = name.strip()
        city = city.strip()

        if not name:
            raise ValidationError("道路名称不能为空")
        if not city:
            raise ValidationError("城市名称不能为空")

        # 在沙盒中查找数据
        city_data = TRAFFIC_SANDBOX.get(name)
        if not city_data:
            return ToolResult.failed(f"暂不支持查询道路 '{name}' 的交通状况").to_dict()

        traffic_data = city_data.get(city)
        if not traffic_data:
            return ToolResult.failed(f"暂不支持查询 '{city}' 的 '{name}' 路况").to_dict()

        # 检查状态
        if traffic_data.get("status") == "1":
            return ToolResult.success(traffic_data).to_dict()
        else:
            error_msg = traffic_data.get("info", "交通路况查询失败")
            return ToolResult.failed(error_msg, traffic_data).to_dict()

    except ValidationError as e:
        logger.error(f"交通路况输入验证失败: {e}")
        return ToolResult.failed(f"输入参数错误: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"交通路况工具异常: {e}", exc_info=True)
        return ToolResult.failed(f"内部错误: {str(e)}").to_dict()
