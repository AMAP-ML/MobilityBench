"""周边POI搜索沙盒工具。"""

import json
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from mobility_bench.tools.base import ToolResult
from mobility_bench.tools.common import ValidationError, validate_coordinate, validate_radius
from mobility_bench.tools.decorators import log_io, with_state
from mobility_bench.tools.sandbox.utils import get_sandbox_data_dir

logger = logging.getLogger(__name__)

# === 加载沙盒数据 ===
SANDBOX_PATH = get_sandbox_data_dir() / "search_around_poi_sandbox.json"

if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        POI_SANDBOX = json.load(f)
    logger.info(f"成功加载周边搜索沙盒数据: {len(POI_SANDBOX)} 个坐标")
else:
    POI_SANDBOX = {}
    logger.warning(f"周边搜索沙盒文件未找到: {SANDBOX_PATH}")


@tool
@log_io
@with_state
def search_around_poi(
    location: Annotated[
        str, "中心点坐标，格式为 '经度,纬度'，例如 '116.481499,39.990755'"
    ],
    keywords: Annotated[str | None, "搜索关键词，可选，例如：加油站、餐厅"] = None,
    radius: Annotated[int, "搜索半径，单位米，默认10000"] = 10000,
) -> dict:
    """根据中心点坐标，搜索周边POI信息"""
    try:
        # 输入验证
        validate_coordinate(location, "中心点坐标")
        validate_radius(radius, min_radius=1, max_radius=50000)

        # 在沙盒中查找精确匹配的 location
        location_data = POI_SANDBOX.get(location)
        if not location_data:
            return ToolResult.failed(f"暂不支持查询坐标 '{location}' 周边的POI信息").to_dict()

        # 如果提供了 keywords，尝试匹配；否则返回所有类别
        matched_pois = []
        if keywords:
            keywords_clean = keywords.strip()
            # 尝试直接匹配 key（如 "建设银行"）
            if keywords_clean in location_data:
                matched_pois = location_data[keywords_clean]
            else:
                # 模糊匹配：遍历所有类别，看 POI 名称是否包含关键词
                for category_pois in location_data.values():
                    for poi in category_pois:
                        if keywords_clean in poi.get("name", ""):
                            matched_pois.append(poi)
        else:
            # 无关键词：合并所有类别的 POI
            for category_pois in location_data.values():
                matched_pois.extend(category_pois)

        # 去重（按 name + location）
        seen = set()
        unique_pois = []
        for poi in matched_pois:
            key = (poi.get("name", ""), poi.get("location", ""))
            if key not in seen:
                seen.add(key)
                unique_pois.append(poi)

        if not unique_pois:
            logger.warning(f"在坐标 '{location}' 周边未找到与 '{keywords or '任意'}' 相关的POI")
            return ToolResult.failed(f"在坐标 '{location}' 周边未找到与 '{keywords or '任意'}' 相关的POI").to_dict()

        return ToolResult.success(unique_pois).to_dict()

    except ValidationError as e:
        logger.error(f"周边搜索输入验证失败: {e}")
        return ToolResult.failed(f"输入参数错误: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"周边搜索工具执行异常: {e}", exc_info=True)
        return ToolResult.failed(f"内部错误: {str(e)}").to_dict()
