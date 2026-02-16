"""Answer accuracy evaluation metric."""

import re

from mobility_bench.evaluation.base import BaseMetric, MetricResult


class AnswerMetric(BaseMetric):
    """Decision making / outcome quality evaluation metric.

    Evaluation dimensions:
    - DR: Delivery Rate - whether agent produces complete, executable output
    - FPR: Final Pass Rate - whether solution satisfies all user constraints
    """

    name = "answer"
    description = "Answer accuracy evaluation"

    # Failure pattern keywords
    FAILURE_PATTERNS = [
        r"cannot provide",
        r"not supported",
        r"failed to get",
        r"query failed",
        r"sorry",
        r"unable to complete",
        r"error occurred",
    ]

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
                model_path = self.config.get("model_path", "./model") if self.config else "./model"
                self._model = SentenceTransformer(model_path)
            except Exception:
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
        source_file = ground_truth.get("source_file", "")
        llm_class = ground_truth.get("llm_class", "")

        # Check if delivery is successful
        delivery_success = not self._is_failure(answer)

        # Evaluate accuracy based on task type
        accuracy = 0.0
        if delivery_success:
            accuracy = self._evaluate_by_type(answer, ground_truth, llm_class)

        return MetricResult(
            case_id=case_id,
            metric_name=self.name,
            score=0.0,
            details={
                "source_file": source_file,
                "intent_family": ground_truth.get("intent_family", ""),
                "llm_class": llm_class,
                "DR": 1.0 if delivery_success else 0.0,
                "FPR": accuracy,
            },
        )

    def _is_failure(self, text: str) -> bool:
        """Check if response is a failure."""
        if not text:
            return True

        for pattern in self.FAILURE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True

        return False

    def _evaluate_by_type(
        self,
        answer: str,
        ground_truth: dict,
        llm_class: str,
    ) -> float:
        """Evaluate accuracy based on task type."""
        if "distance" in llm_class.lower():
            return self._evaluate_distance(answer, ground_truth)
        elif "weather" in llm_class.lower():
            return self._evaluate_weather(answer, ground_truth)
        elif "poi" in llm_class.lower() or "location" in llm_class.lower():
            return self._evaluate_poi(answer, ground_truth)
        elif "route" in llm_class.lower() or "navigation" in llm_class.lower():
            return self._evaluate_route(answer, ground_truth)
        else:
            return self._evaluate_general(answer, ground_truth)

    def _evaluate_distance(self, answer: str, ground_truth: dict) -> float:
        """Evaluate distance query result."""
        # Extract numbers from answer
        numbers = re.findall(r"(\d+\.?\d*)\s*(km|kilometer|mile|m|meter)", answer, re.IGNORECASE)
        if not numbers:
            return 0.0

        # Convert to kilometers
        pred_km = 0
        for num, unit in numbers:
            value = float(num)
            if unit.lower() in ["m", "meter"]:
                value = value / 1000
            pred_km = max(pred_km, value)

        # Get ground truth
        gt_distance = ground_truth.get("route_ans", "")
        if not gt_distance:
            return 0.5  # Cannot verify, give medium score

        # Extract ground truth distance
        gt_numbers = re.findall(r"(\d+\.?\d*)", str(gt_distance))
        if not gt_numbers:
            return 0.5

        gt_km = float(gt_numbers[0])
        if gt_km > 1000:  # Might be in meters
            gt_km = gt_km / 1000

        # Calculate error
        if gt_km == 0:
            return 1.0 if pred_km == 0 else 0.0

        error = abs(pred_km - gt_km) / gt_km
        if error <= self.distance_tolerance:
            return 1.0
        elif error <= self.distance_tolerance * 2:
            return 0.5
        else:
            return 0.0

    def _evaluate_weather(self, answer: str, ground_truth: dict) -> float:
        """Evaluate weather query result."""
        gt_weather = ground_truth.get("weather_description", "")
        if not gt_weather:
            return 0.5

        return self._compute_similarity(answer, str(gt_weather))

    def _evaluate_poi(self, answer: str, ground_truth: dict) -> float:
        """Evaluate POI query result."""
        gt_poi = ground_truth.get("poi_result", {})
        if not gt_poi:
            return 0.5

        # Check if POI name is in answer
        if isinstance(gt_poi, dict):
            poi_name = gt_poi.get("name", "")
            if poi_name and poi_name in answer:
                return 1.0

        return self._compute_similarity(answer, str(gt_poi))

    def _evaluate_route(self, answer: str, ground_truth: dict) -> float:
        """Evaluate route planning result."""
        # Check if route information keywords are present
        route_keywords = ["meter", "kilometer", "minute", "hour", "via", "route", "km", "min"]
        found = sum(1 for kw in route_keywords if kw.lower() in answer.lower())

        if found >= 2:
            return 1.0
        elif found >= 1:
            return 0.5
        else:
            return 0.0

    def _evaluate_general(self, answer: str, ground_truth: dict) -> float:
        """General evaluation."""
        # Check answer length
        if len(answer) < 10:
            return 0.0

        # Score based on content richness
        if len(answer) > 100:
            return 0.8
        elif len(answer) > 50:
            return 0.6
        else:
            return 0.4

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Compute text similarity."""
        if not text1 or not text2:
            return 0.0

        model = self._get_similarity_model()

        if model == "simple":
            words1 = set(text1.split())
            words2 = set(text2.split())
            if not words1 or not words2:
                return 0.0
            overlap = len(words1 & words2)
            return overlap / max(len(words1), len(words2))

        try:
            from sentence_transformers import util
            emb1 = model.encode([text1])
            emb2 = model.encode([text2])
            sim = util.cos_sim(emb1, emb2)
            return float(sim[0][0])
        except Exception:
            return 0.0
