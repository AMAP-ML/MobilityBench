"""Planning process evaluation metric."""

import re

from mobility_bench.evaluation.base import BaseMetric, MetricResult


class PlanningMetric(BaseMetric):
    """Planning process evaluation metric.

    Evaluation dimensions:
    - DEC_P: Decomposition Precision - proportion of ground-truth steps covered by predicted steps
    - DEC_R: Decomposition Recall - proportion of predicted steps that match ground-truth steps
    """

    name = "planning"
    description = "Planning process evaluation"

    # task_scenario -> (required steps, dependency edges)
    TASK_SCENARIO_TO_GOLDEN = {
        "POI Query": (["定位"], []),
        "Geolocation Query": (["定位"], []),
        "Nearby Query": (["定位", "周边搜"], [("定位", "周边搜")]),
        "Weather Query": (["天气查询"], []),
        "Traffic Info Query": (["定位", "路况查询"], [("定位", "路况查询")]),
        "Route Property Query": (["定位", "路线规划"], [("定位", "路线规划")]),
        "Arrival/Departure Time Query": (["定位", "驾车路线规划", "时间倒推计算"], [("定位", "驾车路线规划"), ("驾车路线规划", "时间倒推计算")]),
        "Point-to-Point Planning": (["定位", "路线规划"], [("定位", "路线规划")]),
        "Multi-stop Planning": (["定位", "途径点路线规划"], [("定位", "途径点路线规划")]),
        "Option-Constrained Route Planning": (["定位", "有偏好的路线规划"], [("定位", "有偏好的路线规划")]),
        "Route-Constrained Planning": (["定位", "路线规划"], [("定位", "路线规划")]),
    }

    # Atomic task regex patterns
    ATOMIC_TASK_REGEX = {
        "定位": r"(查询|获取|得到|查找|了解|定位|我在哪|搜一下|模糊信息坐标查询|坐标查询|POI查询|地点查询).*?(位置|坐标|经纬度|当前位置|起点|在哪|地址|：)|"
                r"(位置|坐标|经纬度|当前位置|起点|在哪|地址).*?(查询|获取|得到|查找|了解|定位|我在哪|搜一下)",
        "路况查询": r"(查询|获取|得到|查找|了解|搜一下).*?(路况|拥堵|堵车|交通状况|通行情况)",
        "天气查询": r"(查询|获取|得到|查找|了解|搜一下|查一下).*?(天气|气温|温度|下雨|晴天|预报|气候)|"
                    r"(天气|气温|温度|下雨|晴天|预报|气候).*?(查询|获取|得到|查找|了解|搜一下|查一下)",
        "步行路线规划": r"((步行|走路|走).*?(路线规划|规划路线|怎么走|导航|路径|规划))|"
                       r"((路线规划|规划路线|怎么走|导航|路径|规划).*?(步行|走路|走))",
        "骑行路线规划": r"((骑行|骑车|自行车|单车).*?(路线规划|规划路线|怎么走|导航|路径|规划))|"
                       r"((路线规划|规划路线|怎么走|导航|路径|规划).*?(骑行|骑车|自行车|单车))",
        "公交路线规划": r"((公交|坐公交|乘公交|公交车|巴士|[\d]+路).*?(路线规划|规划路线|怎么走|导航|路径|规划))|"
                       r"((路线规划|规划路线|怎么走|导航|路径|规划).*?(公交|坐公交|乘公交|公交车|巴士|[\d]+路))",
        "驾车路线规划": r"((驾车|开车|自驾).*?(路线规划|规划路线|怎么走|导航|路径|规划))|"
                       r"((路线规划|规划路线|怎么走|导航|路径|规划).*?(驾车|开车|自驾))",
        "有偏好的路线规划": r"((偏好|避开|避免|最短|最快|高速|不走高速|最少红绿灯|高速优先).*?(路线规划|规划路线|怎么走|导航|路径|规划))|"
                          r"((路线规划|规划路线|怎么走|导航|路径|规划).*?(偏好|避开|避免|最短|最快|高速|不走高速|最少红绿灯|高速优先))|"
                          r"(驾车路线规划.*?(不走高速|高速优先|避开|偏好))",
        "途径点路线规划": r"((途径点|途经点|中转点|经过|途径|途经.*?点|路过.*?点|经停).*?(路线规划|规划路线|怎么走|导航|路径|规划))|"
                        r"((路线规划|规划路线|怎么走|导航|路径|规划).*?(途径点|途经点|中转点|经过|途径|途经.*?点|路过.*?点|经停))",
        "路线规划": r"(路线规划|规划路线|怎么走|导航|路径|算路)",
        "公交信息查询": r"(查询|获取|得到|查找|了解|搜一下).*?(公交|公交车|巴士).*?(信息|站台|首末班)",
        "路径规划查询距离": r"(路线规划|规划路线|怎么走|导航|路径|计算|查询).*?(距离|多远|公里|路程|到.*的距离)",
        "时间倒推计算": r"(出发时间|什么时候出发|几点走|提前多久|倒推|推算)",
        "周边搜": r"(周边|附近|周围|旁边|邻近).*?(搜索|找|查|有什么|有哪些)|"
                 r"(搜索|找|查|有什么|有哪些).*?(周边|附近|周围|旁边|邻近)"
    }

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.alpha = config.get("alpha", 0.8) if config else 0.8
        self.beta = config.get("beta", 0.2) if config else 0.2

    def compute(
        self,
        case_id: str,
        prediction: dict,
        ground_truth: dict,
    ) -> MetricResult:
        """Compute single evaluation result."""
        task_scenario = ground_truth.get("task_scenario", "")
        steps_text = prediction.get("steps", "")

        # Get scenario configuration based on task_scenario
        gold_steps, gold_edges = self._get_golden_config(task_scenario)

        if not gold_steps:
            return MetricResult(
                case_id=case_id,
                metric_name=self.name,
                score=1.0,
                details={
                    "task_scenario": task_scenario,
                    "intent_family": ground_truth.get("intent_family", ""),
                    "note": "No standard configuration"
                },
            )

        # Extract steps from prediction text
        pred_steps = self._extract_steps(steps_text)

        # Calculate DEC metric
        dec_recall, dec_precision, dec_score = self._compute_dec(pred_steps, gold_steps)

        return MetricResult(
            case_id=case_id,
            metric_name=self.name,
            score=0.0,
            details={
                "task_scenario": task_scenario,
                "intent_family": ground_truth.get("intent_family", ""),
                "DEC_P": dec_precision,
                "DEC_R": dec_recall,
            },
        )

    def _get_golden_config(self, task_scenario: str) -> tuple:
        """Get scenario standard configuration based on task_scenario."""
        if not task_scenario:
            return ([], [])

        # Try exact match
        if task_scenario in self.TASK_SCENARIO_TO_GOLDEN:
            return self.TASK_SCENARIO_TO_GOLDEN[task_scenario]

        # Try partial match
        for key, value in self.TASK_SCENARIO_TO_GOLDEN.items():
            if key in task_scenario or task_scenario in key:
                return value

        return ([], [])

    def _extract_steps(self, text: str) -> list:
        """Extract steps from text."""
        if not text:
            return []

        steps = []
        for task_name, pattern in self.ATOMIC_TASK_REGEX.items():
            if re.search(pattern, text, re.IGNORECASE):
                steps.append(task_name)

        return steps

    def _compute_dec(
        self,
        pred_steps: list,
        gold_steps: list,
    ) -> tuple:
        """Calculate decision coverage metric."""
        if not gold_steps:
            return 1.0, 1.0, 1.0

        # Calculate hits
        pred_set = set(pred_steps)
        gold_set = set(gold_steps)
        hits = len(pred_set & gold_set)

        # Recall
        recall = hits / len(gold_set) if gold_set else 0

        # Precision
        precision = hits / len(pred_set) if pred_set else 0

        # Composite score
        score = self.alpha * recall + self.beta * precision

        return round(recall, 4), round(precision, 4), round(score, 4)

    def _compute_dep(
        self,
        pred_steps: list,
        gold_edges: list,
    ) -> tuple:
        """Calculate dependency execution metric."""
        if not gold_edges:
            return 1.0, 1.0

        # Check if each edge is satisfied
        satisfied = 0
        for src, dst in gold_edges:
            # Check if src appears before dst
            try:
                src_idx = pred_steps.index(src) if src in pred_steps else -1
                dst_idx = pred_steps.index(dst) if dst in pred_steps else -1

                if src_idx >= 0 and dst_idx >= 0 and src_idx < dst_idx:
                    satisfied += 1
            except ValueError:
                pass

        recall = satisfied / len(gold_edges)
        return round(recall, 4), round(recall, 4)
