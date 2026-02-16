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

    # Scenario standard configuration: source_file -> (required steps, dependency edges)
    GOLDEN_CONFIG = {
        "std_df_no_traffic": (
            ["locating", "route_planning"],
            [("locating", "route_planning")],
        ),
        "std_depart_time_ans": (
            ["locating", "driving_route_planning", "time_calculation"],
            [("locating", "driving_route_planning"), ("driving_route_planning", "time_calculation")],
        ),
        "std_weather_ans": (
            ["weather_query"],
            [],
        ),
        "std_traffic_ans": (
            ["traffic_query"],
            [],
        ),
        "std_poi_ans": (
            ["poi_query"],
            [],
        ),
    }

    # Atomic task regex patterns
    ATOMIC_TASK_REGEX = {
        "locating": r"(locat|query.*position|get.*coordinate|POI.*query.*coordinate)",
        "driving_route_planning": r"(driv|car).*(route|navigation|planning)",
        "walking_route_planning": r"(walk|foot).*(route|navigation|planning)",
        "cycling_route_planning": r"(cycl|bike|bicycle).*(route|navigation|planning)",
        "transit_route_planning": r"(transit|bus|subway).*(route|navigation|planning)",
        "route_planning": r"(route|navigation).*(planning|query)",
        "weather_query": r"(weather|temperature).*(query|get)",
        "traffic_query": r"(traffic|congestion).*(query|get)",
        "poi_query": r"(POI|location|place).*(query|search)",
        "time_calculation": r"(time|depart).*(calculat|comput)",
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
        source_file = ground_truth.get("source_file", "")
        steps_text = prediction.get("steps", "")

        # Get scenario configuration
        gold_steps, gold_edges = self._get_golden_config(source_file)

        if not gold_steps:
            return MetricResult(
                case_id=case_id,
                metric_name=self.name,
                score=1.0,
                details={"source_file": source_file, "intent_family": ground_truth.get("intent_family", ""), "note": "No standard configuration"},
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
                "source_file": source_file,
                "intent_family": ground_truth.get("intent_family", ""),
                "DEC_P": dec_precision,
                "DEC_R": dec_recall,
            },
        )

    def _get_golden_config(self, source_file: str) -> tuple:
        """Get scenario standard configuration."""
        # Try exact match
        if source_file in self.GOLDEN_CONFIG:
            return self.GOLDEN_CONFIG[source_file]

        # Try partial match
        for key, value in self.GOLDEN_CONFIG.items():
            if key in source_file:
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
