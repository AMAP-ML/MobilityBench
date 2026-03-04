"""Answer accuracy evaluation metric."""

import ast
import json
import logging
import re
from pathlib import Path

import cpca

from mobility_bench.evaluation.base import BaseMetric, MetricResult

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
logger = logging.getLogger(__name__)

# Comprehensive failure pattern (Chinese)
FAILURE_PATTERN = re.compile(
    r'(无法提供|未能成功|失败|未找到|未缓存|不支持|无可用|'
    r'无法计算|无法直接计算|查询结果异常|工具限制|技术限制|需进一步计算|'
    r'需要进一步计算|没有可用|'
    r'无法获取|暂未获取|未获得|未缓存该.*路线|无法查询到.*路线|暂不支持.*路线规划|'
    r'系统当前仅支持|由于.*限制|由于.*异常|由于.*不支持)',
    re.IGNORECASE
)


def sanitize_ans_string(s: str) -> str:
    """Clean up tool status strings in answer."""
    if not isinstance(s, str):
        return str(s)
    s = s.replace("<ToolStatus.SUCCESS: 0>", "'SUCCESS'")
    s = s.replace("<ToolStatus.FAILED: 1>", "'FAILED'")
    return s


def get_closing_brackets(text: str) -> tuple:
    """Analyze bracket balance in text."""
    stack = []
    in_quote = None
    escape = False
    for char in text:
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if in_quote:
            if char == in_quote:
                in_quote = None
        else:
            if char in ("'", '"'):
                in_quote = char
            elif char == '{':
                stack.append('}')
            elif char == '[':
                stack.append(']')
            elif char == '}':
                if stack and stack[-1] == '}':
                    stack.pop()
            elif char == ']':
                if stack and stack[-1] == ']':
                    stack.pop()
    return in_quote, stack


def try_fix_truncated_string(s: str):
    """Try to parse potentially truncated JSON/dict string."""
    if not isinstance(s, str) or s.lower() == 'nan':
        return None, False
    s = sanitize_ans_string(s.strip())
    try:
        return ast.literal_eval(s), True
    except Exception:
        pass
    # Try progressively shorter substrings
    for i in range(len(s), 0, -1):
        candidate = s[:i].strip()
        if not candidate:
            continue
        if candidate[-1] in (',', ':', '+', '-'):
            candidate = candidate[:-1].strip()
        in_quote, stack = get_closing_brackets(candidate)
        fixed = candidate
        if in_quote:
            fixed += in_quote
        while stack:
            fixed += stack.pop()
        try:
            return ast.literal_eval(fixed), True
        except Exception:
            continue
    return None, False


def extract_coords(text: str) -> str | None:
    """Extract first coordinate from text."""
    if not isinstance(text, str):
        return None
    match = re.search(r'(\d{2,3}\.\d+),\s*(\d{1,2}\.\d+)', text)
    return f"{match.group(1)},{match.group(2)}" if match else None


def extract_all_coords(text: str) -> list[tuple[float, float]]:
    """Extract all coordinates from text as (lng, lat) tuples."""
    if not isinstance(text, str):
        return []
    matches = re.findall(r'(\d{2,3}\.\d+),\s*(\d{1,2}\.\d+)', text)
    coords = []
    for lng_str, lat_str in matches:
        try:
            lng, lat = float(lng_str), float(lat_str)
            # Basic validation: China coordinates roughly 73-135 lng, 18-54 lat
            if 70 <= lng <= 140 and 15 <= lat <= 55:
                coords.append((lng, lat))
        except ValueError:
            continue
    return coords


def haversine_distance(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """Calculate distance between two coordinates in kilometers using Haversine formula."""
    from math import radians, cos, sin, asin, sqrt
    
    # Convert to radians
    lng1, lat1, lng2, lat2 = map(radians, [lng1, lat1, lng2, lat2])
    
    # Haversine formula
    dlng = lng2 - lng1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
    c = 2 * asin(sqrt(a))
    
    # Earth radius in km
    r = 6371
    return c * r


def extract_route_index_from_answer(answer: str) -> str | None:
    """Extract recommended route index from reporter answer."""
    # Try to parse JSON from markdown code block
    if '```json' in answer:
        try:
            json_str = answer.split('```json')[1].split('```')[0].strip()
            parsed = json.loads(json_str)
            idx = parsed.get('route_index')
            if idx is not None:
                return str(idx)
        except Exception:
            pass
    # Try to find route_index in raw text
    match = re.search(r'route_index["\s:]+(\d+)', answer)
    if match:
        return match.group(1)
    # Try to find "方案1" or "推荐方案1" etc
    match = re.search(r'(?:推荐)?方案\s*(\d+)', answer)
    if match:
        # Convert to 0-indexed
        return str(int(match.group(1)) - 1)
    return None


def extract_content_from_answer(answer: str) -> str:
    """Extract content field from reporter answer JSON.
    
    For information queries (weather, traffic, POI, etc.), the answer
    is in the 'content' field of the JSON response.
    """
    # Try to parse JSON from markdown code block
    if '```json' in answer:
        try:
            json_str = answer.split('```json')[1].split('```')[0].strip()
            parsed = json.loads(json_str)
            content = parsed.get('content', '')
            if content:
                return content
        except Exception:
            pass
    # Fallback: return original answer
    return answer


class AnswerMetric(BaseMetric):
    """Decision making / outcome quality evaluation metric.

    Evaluation dimensions:
    - DR: Delivery Rate - whether agent produces complete, executable output
    - FPR: Final Pass Rate - whether solution satisfies all user constraints
    """

    name = "answer"
    description = "Answer accuracy evaluation"

    # task_scenario to evaluation type mapping
    TASK_SCENARIO_TO_EVAL_TYPE = {
        "POI Query": "poi",
        "Geolocation Query": "location",
        "Nearby Query": "nearby",
        "Weather Query": "weather",
        "Traffic Info Query": "traffic",
        "Route Property Query": "route_info",
        "Arrival/Departure Time Query": "route_info",
        "Point-to-Point Planning": "route",
        "Multi-stop Planning": "route",
        "Option-Constrained Route Planning": "route",
        "Route-Constrained Planning": "route_custom",
    }

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.similarity_threshold = config.get("similarity_threshold", 0.8) if config else 0.8
        self.distance_tolerance = config.get("distance_tolerance", 0.05) if config else 0.05
        self._model = None

    def _get_similarity_model(self):
        """Lazy load similarity model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                logger.warning("sentence-transformers not installed")
                self._model = "simple"
                return self._model
            try:
                model_path = self.config.get("model_path", "") if self.config else ""
                if not model_path:
                    model_path = str(_PROJECT_ROOT / "embedding-model")
                self._model = SentenceTransformer(model_path)
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")
                self._model = "simple"
        return self._model

    def compute(
        self,
        case_id: str,
        prediction: dict,
        ground_truth: dict,
    ) -> MetricResult:
        """Compute single evaluation result."""
        answer = prediction.get("answer", "")
        task_scenario = ground_truth.get("task_scenario", "")
        
        # Extract content from JSON answer at the beginning
        content = extract_content_from_answer(answer)
        if len(content) == 0:
            content = answer
        
        # Get eval type for type-specific delivery check
        eval_type = self.TASK_SCENARIO_TO_EVAL_TYPE.get(task_scenario, "general")
        
        # Check delivery success based on task type
        delivery_success = self._check_delivery_success(content, answer, eval_type)

        # Evaluate accuracy based on task type
        accuracy = 0.0
        if delivery_success:
            accuracy = self._evaluate_by_type(content, answer, ground_truth, eval_type)

        return MetricResult(
            case_id=case_id,
            metric_name=self.name,
            score=0.0,
            details={
                "task_scenario": task_scenario,
                "intent_family": ground_truth.get("intent_family", ""),
                "DR": 1.0 if delivery_success else 0.0,
                "FPR": accuracy,
            },
        )

    def _check_delivery_success(self, content: str, raw_answer: str, eval_type: str) -> bool:
        """Check if response is successful delivery based on task type.
        
        Args:
            content: Extracted content from JSON answer
            raw_answer: Original answer string
            eval_type: Type of evaluation (route, poi, weather, etc.)
        """
        if not isinstance(content, str) or not content.strip() or content.lower() == 'nan':
            return False
        
        # Type-specific delivery checks
        if eval_type in ("route", "route_custom", "route_info"):
            # Route planning: need route_index or route keywords
            route_idx = extract_route_index_from_answer(raw_answer)
            if route_idx is not None and route_idx != "":
                return True
            # Fallback: check for route keywords
            route_keywords = ["公里", "千米", "km", "分钟", "小时", "路线", "距离", "耗时", "途经"]
            found = sum(1 for kw in route_keywords if kw in content)
            return found >= 2
        
        elif eval_type in ("poi", "location"):
            # POI/Location query: need coordinates
            coords = extract_coords(content)
            if coords:
                return True
            # Or address info
            addr_keywords = ["省", "市", "区", "县", "街道", "路", "号"]
            found = sum(1 for kw in addr_keywords if kw in content)
            return found >= 2
        
        elif eval_type == "nearby":
            # Nearby query: need POI names or list
            poi_keywords = ["店", "馆", "厅", "中心", "广场", "超市", "餐"]
            found = sum(1 for kw in poi_keywords if kw in content)
            return found >= 1 or len(content) > 20
        
        elif eval_type == "weather":
            # Weather query: need weather description
            weather_keywords = ["天气", "晴", "阴", "雨", "雪", "云", "风", "度", "℃", "温"]
            found = sum(1 for kw in weather_keywords if kw in content)
            return found >= 1
        
        elif eval_type == "traffic":
            # Traffic query: need traffic status
            traffic_keywords = ["拥堵", "畅通", "缓行", "路况", "通行"]
            found = sum(1 for kw in traffic_keywords if kw in content)
            return found >= 1
        # Check for general failure patterns
        if FAILURE_PATTERN.search(content):
            return False
        
        return len(content) > 10

    def _evaluate_by_type(
        self,
        content: str,
        raw_answer: str,
        ground_truth: dict,
        eval_type: str,
    ) -> float:
        """Evaluate accuracy based on task type.
        
        Args:
            content: Extracted content from JSON answer
            raw_answer: Original answer string (for route_index extraction)
            ground_truth: Ground truth data
            eval_type: Type of evaluation
        """
        if eval_type == "route":
            return self._evaluate_route(raw_answer, ground_truth)
        elif eval_type == "route_custom":
            return self._evaluate_route_custom(raw_answer, ground_truth)
        elif eval_type == "route_info":
            return self._evaluate_route_info(content, ground_truth)
        elif eval_type == "weather":
            return self._evaluate_weather(content, ground_truth)
        elif eval_type == "poi":
            return self._evaluate_poi(content, ground_truth)
        elif eval_type == "location":
            return self._evaluate_location(content, ground_truth)
        elif eval_type == "nearby":
            return self._evaluate_nearby(content, ground_truth)
        elif eval_type == "traffic":
            return self._evaluate_traffic(content, ground_truth)
        else:
            return self._evaluate_general(content, ground_truth)

    def _evaluate_route(self, answer: str, ground_truth: dict) -> float:
        """Evaluate route planning result.
        
        For route planning, check if the recommended route index matches
        the expected route index from ground truth.
        """
        # Extract recommended route index from answer
        pred_idx = extract_route_index_from_answer(answer)
        # basic route planning
        # print("answer", answer)
        if pred_idx and pred_idx != "-1":
            return 1.0
        
        return 0.0

    
    def _evaluate_route_custom(self, answer: str, ground_truth: dict) -> float:
        """Evaluate route planning result.
        
        For route planning, check if the recommended route index matches
        the expected best route (usually index 0).
        """
        # Extract recommended route index from answer
        pred_idx = extract_route_index_from_answer(answer)
        ans_idx = ground_truth.get("matched_transit_index", "")
        # 
        if (pred_idx == "" or pred_idx == "-1") and int(ans_idx) == 0:
            return 1.0
        if pred_idx and int(pred_idx) == int(ans_idx):
            return 1.0
        
        return 0.0
    
    def _evaluate_route_info(self, content: str, ground_truth: dict) -> float:
        """Evaluate route information result using similarity."""
         # Extract recommended route index from answer
        
        # Fallback: check if answer contains reasonable route information
        route_keywords = ["公里", "千米", "km", "分钟", "小时", "路线", "距离", "耗时", "途经", "米"]
        found = sum(1 for kw in route_keywords if kw in content)
        if found >= 2:
            return 1.0
        return 0.0

    def _evaluate_weather(self, content: str, ground_truth: dict) -> float:
        """Evaluate weather query result using similarity."""
        gt_weather = ground_truth.get("weather_description", "")
        if not gt_weather or str(gt_weather).lower() == 'nan':
            return 0.0
        
        gt_str = str(gt_weather)
        
        # Check if ground truth appears in content
        if gt_str in content:
            return 1.0
        
        # Use similarity comparison
        sim = self._compute_similarity(content, gt_str)
        return 1.0 if sim > self.similarity_threshold else 0.0

    def _evaluate_poi(self, content: str, ground_truth: dict) -> float:
        """Evaluate POI query result by coordinate matching.
        
        Extracts all coordinates from content and checks if any is within 1km
        of the ground truth coordinate.
        """
        # Extract all predicted coordinates from content
        pred_coords = extract_all_coords(content)
        
        # Get ground truth coordinate
        gt_lng, gt_lat = None, None
        
        # First try ans_loc (direct coordinates)
        ans_loc = ground_truth.get("ans_loc", "")
        if ans_loc and str(ans_loc).lower() != 'nan':
            gt_coord_str = str(ans_loc).strip()
            try:
                parts = gt_coord_str.split(',')
                if len(parts) == 2:
                    gt_lng, gt_lat = float(parts[0]), float(parts[1])
            except (ValueError, IndexError):
                pass
        
        # Try poi_result if ans_loc not available
        if gt_lng is None:
            gt_poi = ground_truth.get("poi_result")
            if gt_poi:
                if isinstance(gt_poi, str):
                    gt_poi, ok = try_fix_truncated_string(gt_poi)
                    if not ok:
                        gt_poi = None
                
                if isinstance(gt_poi, dict):
                    gt_coord_str = gt_poi.get("data", {}).get("location")
                    if not gt_coord_str:
                        gt_coord_str = gt_poi.get("location")
                    
                    if gt_coord_str:
                        try:
                            parts = str(gt_coord_str).strip().split(',')
                            if len(parts) == 2:
                                gt_lng, gt_lat = float(parts[0]), float(parts[1])
                        except (ValueError, IndexError):
                            pass
                    
                    # Check name match as fallback
                    poi_name = gt_poi.get("name", "")
                    if not poi_name:
                        poi_name = gt_poi.get("data", {}).get("name", "")
                    if poi_name and poi_name in content:
                        return 1.0
        
        # Check if any predicted coordinate is within 1km of ground truth
        if gt_lng is not None and gt_lat is not None and pred_coords:
            for pred_lng, pred_lat in pred_coords:
                distance = haversine_distance(pred_lng, pred_lat, gt_lng, gt_lat)
                if distance <= 1.0:  # Within 1km
                    return 1.0
        
        return 0.0

    def _evaluate_location(self, content: str, ground_truth: dict) -> float:
        """Evaluate location/address query using cpca or string match."""
        gt_addr = ground_truth.get("formatted_address", "")
        if not gt_addr or str(gt_addr).lower() == 'nan':
            return 0.0
        
        gt_addr_str = str(gt_addr)

        # Try cpca for address parsing (city/district matching)
        try:
            p_addr = cpca.transform([content]).iloc[0]
            g_addr = cpca.transform([gt_addr_str]).iloc[0]
            # Check city and district match
            if (p_addr['市'] and g_addr['市'] and p_addr['市'] == g_addr['市'] and 
                p_addr['区'] and g_addr['区'] and p_addr['区'] == g_addr['区']):
                return 1.0
        except Exception:
            pass

        # Check if formatted_address appears in content
        if gt_addr_str in content:
            return 1.0

        # Fallback: similarity comparison
        sim = self._compute_similarity(content, gt_addr_str)
        return 1.0 if sim > self.similarity_threshold else 0.0

    def _evaluate_nearby(self, content: str, ground_truth: dict) -> float:
        """Evaluate nearby POI search result."""
        gt_near = ground_truth.get("near_poi_ans", "")
        if not gt_near or str(gt_near).lower() == 'nan':
            return 0.0
        # Try to parse and extract POI names
        gt_data, ok = try_fix_truncated_string(str(gt_near))
        
        if ok and isinstance(gt_data, dict):
            # Extract POI names from near_poi_ans.data.pois
            pois = gt_data.get("data", {}).get("pois", [])
            if len(pois) == 0:
                return 1.0
            if pois and isinstance(pois, list):
                # Check if any POI name appears in the content
                for poi in pois[:5]:  # Check first 5 POIs
                    if isinstance(poi, dict):
                        poi_name = poi.get("name", "")
                        if poi_name and poi_name in content:
                            return 1.0
                        # sim
                        if self._compute_similarity(content, poi_name) > self.similarity_threshold:
                            return 1.0
        # Fallback: use similarity
        sim = self._compute_similarity(content, str(gt_near))
        return 1.0 if sim > self.similarity_threshold else 0.0

    def _evaluate_traffic(self, content: str, ground_truth: dict) -> float:
        """Evaluate traffic info query.
        Rule: if at least 2 traffic keywords appear in gt_desc, then those 2 must
        also appear in content to score 1. Otherwise use original fallback.
        """
        traffic_keywords = ["拥堵", "畅通", "缓行", "通行", "拥挤", "顺畅", "双向"]

        gt_ans = ground_truth.get("ans", "")
        if gt_ans and str(gt_ans).lower() != "nan":
            gt_data, ok = try_fix_truncated_string(str(gt_ans))
            if ok and isinstance(gt_data, dict):
                gt_desc = gt_data.get("trafficinfo", {}).get("description", "") or ""
                if gt_desc:
                    # New rule: if >=2 keywords exist in gt_desc, require at least 2 of those in content
                    gt_kws = [kw for kw in traffic_keywords if kw in gt_desc]
                    if len(gt_kws) >= 2:
                        matched = sum(1 for kw in gt_kws if kw in content)
                        return 1.0 if matched >= 2 else 0.0

                    # Otherwise keep original behavior
                    if gt_desc in content:
                        return 1.0
                    sim = self._compute_similarity(content, gt_desc)
                    return 1.0 if sim > self.similarity_threshold else 0.0

        # Fallback: check for traffic keywords in content
        found = sum(1 for kw in traffic_keywords if kw in content)
        if found >= 2:
            return 1.0
        elif found >= 1:
            return 0.5
        return 0.0


    def _evaluate_general(self, content: str, ground_truth: dict) -> float:
        """General evaluation fallback."""
        # Try route_ans
        if ground_truth.get("route_ans"):
            return self._evaluate_route(content, ground_truth)
        # Try weather
        if ground_truth.get("weather_description"):
            return self._evaluate_weather(content, ground_truth)
        # Try POI
        if ground_truth.get("poi_result"):
            return self._evaluate_poi(content, ground_truth)
        return 0.0

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Compute text similarity using embedding model."""
        if not text1 or not text2:
            return 0.0

        if text2 in text1 or text1 in text2:
            return 1.0

        model = self._get_similarity_model()

        if model == "simple":
            chars1 = set(text1)
            chars2 = set(text2)
            if not chars1 or not chars2:
                return 0.0
            intersection = len(chars1 & chars2)
            union = len(chars1 | chars2)
            return intersection / union if union else 0.0

        try:
            from sentence_transformers import util
            emb1 = model.encode([text1])
            emb2 = model.encode([text2])
            sim = util.cos_sim(emb1, emb2)
            return float(sim[0][0])
        except Exception:
            return 0.0
