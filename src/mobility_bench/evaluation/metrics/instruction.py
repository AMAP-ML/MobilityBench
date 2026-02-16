"""Instruction understanding evaluation metric."""


from mobility_bench.evaluation.base import BaseMetric, MetricResult


class InstructionMetric(BaseMetric):
    """Instruction understanding evaluation metric.

    Evaluation dimensions:
    - intent_score: Intent understanding score (semantic similarity)
    - intent_correct: Whether intent is correct
    - info_extraction_correct: Whether information extraction is complete
    """

    name = "instruction"
    description = "Instruction understanding evaluation"

    # LLM_CLASS to intent and slots mapping
    LLM_CLASS_TO_INTENT_SLOTS = {
        "complex-departure-time": ("Departure time planning", ["query_start_poi", "query_end_poi"]),
        "route-planning-driving": ("Driving route planning", ["query_start_poi", "query_end_poi"]),
        "route-planning-walking": ("Walking route planning", ["query_start_poi", "query_end_poi"]),
        "route-planning-cycling": ("Cycling route planning", ["query_start_poi", "query_end_poi"]),
        "route-planning-transit": ("Transit route planning", ["query_start_poi", "query_end_poi"]),
        "route-planning-taxi": ("Taxi route planning", ["query_start_poi", "query_end_poi"]),
        "info-query-weather": ("Weather query", ["city"]),
        "info-query-poi": ("POI query", ["keywords"]),
        "info-query-traffic": ("Traffic query", ["road_name", "city"]),
        "info-query-distance": ("Distance query", ["query_start_poi", "query_end_poi"]),
        "info-query-location": ("Location query", ["keywords"]),
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
                model_path = self.config.get("model_path", "./model") if self.config else "./model"
                self._model = SentenceTransformer(model_path)
            except Exception:
                # Use simple string matching as fallback
                self._model = "simple"
        return self._model

    def compute(
        self,
        case_id: str,
        prediction: dict,
        ground_truth: dict,
    ) -> MetricResult:
        """Compute single evaluation result."""
        llm_class = ground_truth.get("llm_class", "")
        thinking = prediction.get("thinking", "")
        pred_intent = prediction.get("intent", "")
        steps = prediction.get("steps", "")

        # Get expected intent and slots
        expected_intent, required_slots = self._get_intent_slots(llm_class)

        # Calculate intent similarity
        intent_score = self._compute_similarity(pred_intent, expected_intent)
        intent_correct = intent_score >= self.similarity_threshold

        # Check slot extraction
        combined_text = f"{thinking} {steps}"
        slots_found = {}
        for slot in required_slots:
            # Simple check if slot is mentioned in text
            slot_value = ground_truth.get(slot, "")
            if slot_value and str(slot_value) in combined_text:
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
                "llm_class": llm_class,
                "intent_score": intent_score,
                "intent_correct": intent_correct,
                "info_extraction_correct": info_extraction_correct,
                "slots_found": slots_found,
            },
        )

    def _get_intent_slots(self, llm_class: str) -> tuple:
        """Get intent and slots."""
        # Try exact match
        if llm_class in self.LLM_CLASS_TO_INTENT_SLOTS:
            return self.LLM_CLASS_TO_INTENT_SLOTS[llm_class]

        # Try partial match
        for key, value in self.LLM_CLASS_TO_INTENT_SLOTS.items():
            if key in llm_class or llm_class in key:
                return value

        # Default return
        return ("Unknown intent", [])

    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Compute text similarity."""
        if not text1 or not text2:
            return 0.0

        model = self._get_similarity_model()

        if model == "simple":
            # Simple word overlap similarity
            words1 = set(text1.lower().split())
            words2 = set(text2.lower().split())
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
