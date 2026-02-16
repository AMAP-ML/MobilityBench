"""Evaluation metric base classes."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class MetricResult:
    """Single evaluation result."""

    case_id: str
    metric_name: str
    score: float
    details: dict = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "metric_name": self.metric_name,
            "score": self.score,
            "details": self.details,
            "error": self.error,
        }


@dataclass
class MetricSummary:
    """Aggregated evaluation summary."""

    metric_name: str
    average_score: float
    total_cases: int
    successful_cases: int
    failed_cases: int
    sub_scores: dict = field(default_factory=dict)
    by_category: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "metric_name": self.metric_name,
            "average_score": self.average_score,
            "total_cases": self.total_cases,
            "successful_cases": self.successful_cases,
            "failed_cases": self.failed_cases,
            "sub_scores": self.sub_scores,
            "by_category": self.by_category,
            "extra": self.extra,
        }


class BaseMetric(ABC):
    """Base class for evaluation metrics.

    All evaluation metrics must inherit this class and implement
    the compute and aggregate methods.
    """

    name: str = "base"
    description: str = "Base evaluation metric"

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    @abstractmethod
    def compute(
        self,
        case_id: str,
        prediction: dict,
        ground_truth: dict,
    ) -> MetricResult:
        """Compute single result.

        Args:
            case_id: Case ID
            prediction: Model prediction result
            ground_truth: Ground truth

        Returns:
            Evaluation result
        """
        pass

    def batch_compute(
        self,
        predictions: list[dict],
        ground_truths: list[dict],
    ) -> list[MetricResult]:
        """Batch computation.

        Args:
            predictions: List of predictions
            ground_truths: List of ground truths

        Returns:
            List of evaluation results
        """
        results = []
        for pred, gt in zip(predictions, ground_truths, strict=False):
            case_id = pred.get("case_id", gt.get("case_id", "unknown"))
            try:
                result = self.compute(case_id, pred, gt)
                results.append(result)
            except Exception as e:
                results.append(MetricResult(
                    case_id=case_id,
                    metric_name=self.name,
                    score=0.0,
                    error=str(e),
                ))
        return results

    # Fields to skip when aggregating sub-dimensions from details
    _SKIP_DETAIL_FIELDS = {"source_file", "llm_class", "slots_found", "pred_steps", "gold_steps", "note"}

    def aggregate(self, results: list[MetricResult]) -> MetricSummary:
        """Aggregate evaluation results.

        Args:
            results: List of evaluation results

        Returns:
            Summary result with sub-dimension averages
        """
        if not results:
            return MetricSummary(
                metric_name=self.name,
                average_score=0.0,
                total_cases=0,
                successful_cases=0,
                failed_cases=0,
            )

        successful = [r for r in results if r.error is None]
        failed = [r for r in results if r.error is not None]
        scores = [r.score for r in successful]

        # Aggregate numeric sub-dimensions from details
        sub_sums: dict[str, float] = {}
        sub_counts: dict[str, int] = {}
        for r in successful:
            if not r.details:
                continue
            for key, value in r.details.items():
                if key in self._SKIP_DETAIL_FIELDS:
                    continue
                if isinstance(value, bool):
                    value = 1.0 if value else 0.0
                if isinstance(value, (int, float)):
                    sub_sums[key] = sub_sums.get(key, 0.0) + float(value)
                    sub_counts[key] = sub_counts.get(key, 0) + 1

        sub_scores = {}
        for key in sub_sums:
            if sub_counts[key] > 0:
                sub_scores[key] = round(sub_sums[key] / sub_counts[key], 4)

        return MetricSummary(
            metric_name=self.name,
            average_score=sum(scores) / len(scores) if scores else 0.0,
            total_cases=len(results),
            successful_cases=len(successful),
            failed_cases=len(failed),
            sub_scores=sub_scores,
        )

    def to_dataframe(self, results: list[MetricResult]) -> pd.DataFrame:
        """Convert results to DataFrame.

        Args:
            results: List of evaluation results

        Returns:
            DataFrame
        """
        records = []
        for r in results:
            record = {
                "case_id": r.case_id,
                "metric_name": r.metric_name,
                "score": r.score,
                "error": r.error,
            }
            # Expand details
            for key, value in r.details.items():
                record[key] = value
            records.append(record)

        return pd.DataFrame(records)

    def aggregate_by_category(
        self,
        results: list[MetricResult],
        category_key: str = "source_file",
    ) -> dict[str, MetricSummary]:
        """Aggregate results by category.

        Args:
            results: List of evaluation results
            category_key: Category key name

        Returns:
            Summary results by category
        """
        # Group by category
        by_category = {}
        for r in results:
            category = r.details.get(category_key, "unknown")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(r)

        # Aggregate each category
        summaries = {}
        for category, cat_results in by_category.items():
            summaries[category] = self.aggregate(cat_results)

        return summaries
