"""POI查询沙盒工具。"""

import json
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from mobility_bench.tools.base import ToolResult
from mobility_bench.tools.common import ValidationError, validate_address, validate_city
from mobility_bench.tools.decorators import log_io, with_state
from mobility_bench.tools.sandbox.utils import get_sandbox_data_dir

logger = logging.getLogger(__name__)

# ===== 加载 JSON 数据 =====
# 结构: {keyword: {city: poi_info}}
SANDBOX_PATH = get_sandbox_data_dir() / "nested_poi_data.json"
MOCK_POI_DATA = {}
if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        MOCK_POI_DATA = json.load(f)
else:
    logger.warning(f"沙盒数据未找到: {SANDBOX_PATH}")


def _lookup_real_result(keyword: str, city: str | None) -> dict | None:
    """
    查找逻辑：
    1. 如果 keyword 不存在 → 返回 None
    2. 如果 keyword 存在：
       - 尝试用 city 精确匹配（标准化后）
       - 匹配失败 或 未提供 city → 返回第一个结果（按 JSON 顺序）
    """
    if keyword not in MOCK_POI_DATA:
        return None

    city_map = MOCK_POI_DATA[keyword]

    # 如果提供了 city，尝试匹配
    if city is not None and city != "":
        city_clean = city.rstrip("市") if city.endswith("市") else city
        for stored_city, poi_info in city_map.items():
            stored_clean = stored_city.rstrip("市") if stored_city.endswith("市") else stored_city
            if city_clean == stored_clean:
                return poi_info

    # 未提供 city 或匹配失败 → 返回第一个结果
    first_result = next(iter(city_map.values()))
    return first_result


@tool
@log_io
@with_state
def query_poi(
    keywords: Annotated[str, "要查询的关键词，例如：天安门、肯德基等"],
    city: Annotated[str | None, "城市名称，可选，例如：北京、上海"] = None,
) -> dict:
    """根据模糊的位置信息，搜索得到准确的位置信息和坐标"""
    try:
        validated_keywords = validate_address(keywords)
        effective_city = city

        if effective_city:
            effective_city = validate_city(effective_city)

        # 查找结果
        real_result = _lookup_real_result(validated_keywords, effective_city)

        if real_result is None:
            logger.info(f"关键词 '{validated_keywords}' 在沙盒数据中未找到")
            return ToolResult.failed(f"POI '{validated_keywords}' 在沙盒中未找到").to_dict()

        # 构建返回结果
        filtered_poi = {
            "location": real_result.get("location", ""),
            "name": real_result.get("name", ""),
            "address": real_result.get("address", ""),
        }

        logger.info(f"POI查询成功 - 关键词: '{validated_keywords}', 城市: '{effective_city}'")

        return ToolResult.success(filtered_poi).to_dict()

    except ValidationError as e:
        return ToolResult.failed(f"输入参数错误: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"POI查询异常: {e}", exc_info=True)
        return ToolResult.failed(f"内部错误: {str(e)}").to_dict()
