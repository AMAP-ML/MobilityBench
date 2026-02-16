"""Efficiency evaluation metric."""


from mobility_bench.evaluation.base import BaseMetric, MetricResult


class EfficiencyMetric(BaseMetric):
    """Efficiency evaluation metric.

    Evaluation dimensions:
    - total_tokens: Total token consumption
    - planner_tokens: Planner token consumption
    - worker_tokens: Worker token consumption
    - reporter_tokens: Reporter token consumption
    - execution_time: Execution time
    """

    name = "efficiency"
    description = "Efficiency evaluation"

    def __init__(self, config: dict | None = None):
        super().__init__(config)

    def compute(
        self,
        case_id: str,
        prediction: dict,
        ground_truth: dict,
    ) -> MetricResult:
        """Compute single evaluation result."""
        token_usage = prediction.get("token_usage", {})

        # Extract tokens for each stage
        planner_tokens = self._extract_tokens(token_usage, "Planner")
        worker_tokens = self._extract_tokens(token_usage, "Worker")
        reporter_tokens = self._extract_tokens(token_usage, "Reporter")

        total_tokens = planner_tokens + worker_tokens + reporter_tokens

        # Execution time
        execution_time = token_usage.get("processing_time_seconds", 0)
        if not execution_time:
            execution_time = token_usage.get("execution_time", 0)

        # Efficiency score (based on token consumption, lower is better)
        # Assuming reasonable range is 1000-10000 tokens
        if total_tokens <= 1000:
            score = 1.0
        elif total_tokens <= 5000:
            score = 0.8
        elif total_tokens <= 10000:
            score = 0.6
        elif total_tokens <= 20000:
            score = 0.4
        else:
            score = 0.2

        return MetricResult(
            case_id=case_id,
            metric_name=self.name,
            score=score,
            details={
                "source_file": ground_truth.get("source_file", ""),
                "total_tokens": total_tokens,
                "planner_tokens": planner_tokens,
                "worker_tokens": worker_tokens,
                "reporter_tokens": reporter_tokens,
                "execution_time": execution_time,
            },
        )

    def _extract_tokens(self, data: dict, stage: str) -> int:
        """Extract token count for specific stage."""
        # Try multiple naming conventions
        keys_to_try = [
            f"{stage}_total_tokens",
            f"{stage}_Total_Tokens",
            f"{stage} Total Tokens",
        ]

        for key in keys_to_try:
            if key in data:
                try:
                    return int(data[key])
                except (ValueError, TypeError):
                    pass

        # Try calculating prompt + completion
        prompt_keys = [f"{stage}_prompt_tokens", f"{stage} Prompt Tokens"]
        completion_keys = [f"{stage}_completion_tokens", f"{stage} Completion Tokens"]

        prompt = 0
        completion = 0

        for key in prompt_keys:
            if key in data:
                try:
                    prompt = int(data[key])
                    break
                except (ValueError, TypeError):
                    pass

        for key in completion_keys:
            if key in data:
                try:
                    completion = int(data[key])
                    break
                except (ValueError, TypeError):
                    pass

        return prompt + completion
