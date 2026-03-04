"""Instruction understanding evaluation metric."""

from pathlib import Path

from mobility_bench.evaluation.base import BaseMetric, MetricResult

# Resolve project root from this file's location (src/mobility_bench/evaluation/metrics/instruction.py)
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


class InstructionMetric(BaseMetric):
    """Instruction understanding evaluation metric.

    Evaluation dimensions:
    - ID: Intent Detection - whether agent correctly identifies query intent (similarity >= threshold)
    - IE: Information Extraction - whether agent extracts all constraints/slots correctly
    """

    name = "instruction"
    description = "Instruction understanding evaluation"

    # task_scenario to intent and slots mapping
    TASK_SCENARIO_TO_INTENT_SLOTS = {
        "POI Query": ("地点查询", ["query"]),
        "Geolocation Query": ("位置查询", ["longitude", "latitude"]),
        "Nearby Query": ("附近周边搜索", ["near_poi_info", "query_poi"]),
        "Weather Query": ("天气查询", ["city", "time"]),
        "Traffic Info Query": ("拥堵", ["road"]),
        "Route Property Query": ("距离", ["query_start_poi", "query_end_poi"]),
        "Arrival/Departure Time Query": ("出发时间", ["query_start_poi", "query_end_poi"]),
        "Point-to-Point Planning": ("路线规划", ["query_start_poi", "query_end_poi"]),
        "Multi-stop Planning": ("路线规划", ["query_start_poi", "query_transit_poi", "query_end_poi"]),
        "Option-Constrained Route Planning": ("路线规划", ["query_start_poi", "query_end_poi"]),
        "Route-Constrained Planning": ("路线规划", ["query_start_poi", "query_end_poi"]),
    }

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        self.similarity_threshold = config.get("similarity_threshold", 0.7) if config else 0.7
        self._model = None

    def _get_similarity_model(self):
        """Lazy load similarity model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                import logging
                logging.getLogger(__name__).warning(
                    "sentence-transformers not installed. "
                    "Install with: uv sync --extra eval"
                )
                self._model = "simple"
                return self._model

            try:
                model_path = self.config.get("model_path", "") if self.config else ""
                if not model_path:
                    model_path = str(_PROJECT_ROOT / "embedding-model")
                self._model = SentenceTransformer(model_path)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Failed to load embedding model: {e}. Using simple fallback."
                )
                self._model = "simple"
        return self._model

    def compute(
        self,
        case_id: str,
        prediction: dict,
        ground_truth: dict,
    ) -> MetricResult:
        """Compute single evaluation result."""
        task_scenario = ground_truth.get("task_scenario", "")
        thinking = prediction.get("thinking", "")
        pred_intent = prediction.get("intent", "")
        steps = prediction.get("steps", "")

        # Get expected intent and slots based on task_scenario
        expected_intent, required_slots = self._get_intent_slots(task_scenario)

        # Calculate intent similarity
        intent_score = self._compute_similarity(pred_intent, expected_intent)
        intent_correct = intent_score >= self.similarity_threshold

        # Check slot extraction
        combined_text = f"{thinking} {steps}"
        slots_found = {}
        for slot in required_slots:
            # Simple check if slot is mentioned in text
            slot_value = ground_truth.get(slot, "")
            if not slot_value:
                # Slot has no ground truth value, skip it
                continue
            if str(slot_value) in combined_text:
                slots_found[slot] = True
            else:
                slots_found[slot] = False

        info_extraction_correct = all(slots_found.values()) if slots_found else True

        return MetricResult(
            case_id=case_id,
            metric_name=self.name,
            score=0.0,
            details={
                "source_file": ground_truth.get("source_file", ""),
                "intent_family": ground_truth.get("intent_family", ""),
                "task_scenario": task_scenario,
                "ID": 1.0 if intent_correct else 0.0,
                "IE": 1.0 if info_extraction_correct else 0.0,
            },
        )

    def _get_intent_slots(self, task_scenario: str) -> tuple:
        """Get intent and slots based on task_scenario."""
        if not task_scenario:
            return ("Unknown intent", [])

        # Try exact match
        if task_scenario in self.TASK_SCENARIO_TO_INTENT_SLOTS:
            return self.TASK_SCENARIO_TO_INTENT_SLOTS[task_scenario]

        # Try partial match
        for key, value in self.TASK_SCENARIO_TO_INTENT_SLOTS.items():
            if key in task_scenario or task_scenario in key:
                return value

        # Default return
        return ("Unknown intent", [])

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Compute text similarity."""
        if not text1 or not text2:
            return 0.0

        # Substring containment check (handles Chinese text where split() doesn't work)
        if text2 in text1 or text1 in text2:
            return 1.0

        model = self._get_similarity_model()

        if model == "simple":
            # Character-level Jaccard similarity for better CJK support
            chars1 = set(text1.lower())
            chars2 = set(text2.lower())
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
