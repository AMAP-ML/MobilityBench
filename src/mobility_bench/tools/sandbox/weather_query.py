"""天气查询沙盒工具。"""

import json
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from mobility_bench.tools.base import ToolResult
from mobility_bench.tools.common import ValidationError, validate_city
from mobility_bench.tools.decorators import log_io, with_state
from mobility_bench.tools.sandbox.utils import get_sandbox_data_dir

logger = logging.getLogger(__name__)


def normalize_location(name: str) -> str:
    """移除常见行政区后缀，返回核心地名。"""
    if not name or not isinstance(name, str):
        return name
    suffixes = ["省", "市", "县", "区", "自治州", "特别行政区"]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    return name


# === 加载沙盒并构建标准化映射 ===
SANDBOX_PATH = get_sandbox_data_dir() / "weather_sandbox.json"

if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        RAW_SANDBOX = json.load(f)
    logger.info(f"成功加载天气沙盒数据: {len(RAW_SANDBOX)} 个城市")
else:
    RAW_SANDBOX = {}
    logger.warning(f"天气沙盒文件未找到: {SANDBOX_PATH}")

# 构建 {normalized_key: original_key} 映射
# 如果有冲突（如"山东"和"山东省"都变成"山东"），后者会覆盖前者
NORMALIZED_TO_ORIGINAL = {}
for original_key in RAW_SANDBOX:
    norm_key = normalize_location(original_key)
    NORMALIZED_TO_ORIGINAL[norm_key] = original_key


@tool
@log_io
@with_state
def weather_query(
    city: Annotated[str, "城市名称，例如：'北京'、'上海'、'广州'等"],
    need_forecast: Annotated[
        bool, "是否需要未来几天的天气预报，True表示需要预报，False表示只要当前天气"
    ] = False,
) -> dict:
    """查询指定位置的天气信息。"""
    try:
        validated_city = validate_city(city)
        if not validated_city:
            return ToolResult.failed("城市名称不能为空，请提供有效的城市名称").to_dict()

        # 标准化用户输入
        norm_input = normalize_location(validated_city)

        # 在标准化映射中查找
        original_key = NORMALIZED_TO_ORIGINAL.get(norm_input)
        if not original_key:
            return ToolResult.failed(f"暂不支持查询 '{validated_city}' 的天气").to_dict()

        city_data = RAW_SANDBOX[original_key]
        forecast_key = str(need_forecast)  # JSON 中是 "True"/"False"

        if forecast_key in city_data:
            weather_desc = city_data[forecast_key]["weather_description"]
            return ToolResult.success({"weather_description": weather_desc}).to_dict()
        else:
            action = "天气预报" if need_forecast else "当前天气"
            return ToolResult.failed(f"暂无 '{original_key}' 的{action}数据").to_dict()

    except ValidationError as e:
        logger.error(f"天气查询输入验证失败: {e}")
        return ToolResult.failed(f"输入参数错误: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"天气查询工具执行异常: {e}", exc_info=True)
        return ToolResult.failed(f"内部错误: {str(e)}").to_dict()
