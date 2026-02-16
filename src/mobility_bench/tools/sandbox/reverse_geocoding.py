"""逆地理编码沙盒工具。"""

import json
import logging
from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from mobility_bench.tools.base import ToolResult
from mobility_bench.tools.common import ValidationError
from mobility_bench.tools.decorators import log_io, with_state
from mobility_bench.tools.sandbox.utils import get_sandbox_data_dir

logger = logging.getLogger(__name__)

# 加载沙盒数据: {"lat,lon": "address"}
SANDBOX_PATH = get_sandbox_data_dir() / "reverse_geocoding_sandbox.json"

if SANDBOX_PATH.exists():
    with open(SANDBOX_PATH, "r", encoding="utf-8") as f:
        SANDBOX_DATA = json.load(f)
    logger.info(f"成功加载逆地理编码沙盒数据: {len(SANDBOX_DATA)} 条记录")
else:
    SANDBOX_DATA = {}
    logger.warning(f"逆地理编码沙盒文件未找到: {SANDBOX_PATH}")


@tool
@log_io
@with_state
def reverse_geocoding(
    longitude: Annotated[str, "经度"],
    latitude: Annotated[str, "纬度"],
    radius: Annotated[int, "搜索半径，单位：米，默认1000"] = 1000,
) -> dict:
    """根据经纬度坐标进行逆地理编码，查询该位置的详细地址信息。"""
    try:
        # 验证数值范围（仍需转 float）
        lon_val = float(longitude)
        lat_val = float(latitude)
        if not (-180 <= lon_val <= 180):
            raise ValidationError(f"经度应在[-180,180]，实际: {lon_val}")
        if not (-90 <= lat_val <= 90):
            raise ValidationError(f"纬度应在[-90,90]，实际: {lat_val}")
        if not (1 <= radius <= 50000):
            raise ValidationError(f"半径应在[1,50000]米，实际: {radius}")

        # 关键：直接用原始字符串拼接
        key = f"{latitude},{longitude}"
        if key in SANDBOX_DATA:
            address = SANDBOX_DATA[key]
            if not address or not isinstance(address, str):
                return ToolResult.failed(f"地址数据无效 (key='{key}')").to_dict()
            return ToolResult.success({"address": address}).to_dict()
        else:
            logger.info(f"未找到坐标 ({longitude}, {latitude}) 的地址数据")
            return ToolResult.failed(f"未找到坐标 ({longitude}, {latitude}) 的地址数据").to_dict()

    except ValidationError as e:
        return ToolResult.failed(f"输入参数错误: {str(e)}").to_dict()
    except Exception as e:
        logger.error(f"逆地理编码异常: {e}", exc_info=True)
        return ToolResult.failed(f"内部错误: {str(e)}").to_dict()
