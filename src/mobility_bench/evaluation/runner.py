"""Evaluation runner."""

import json
import logging
from pathlib import Path

import pandas as pd

from mobility_bench.config.settings import Settings
from mobility_bench.dataset.loader import DatasetLoader
from mobility_bench.evaluation.registry import MetricRegistry

logger = logging.getLogger(__name__)


class EvaluationRunner:
    """Evaluation runner.

    Coordinates execution of multiple evaluation metrics, result collection and aggregation.
    """

    def __init__(
        self,
        run_dir: Path,
        output_dir: Path,
        ground_truth_path: Path | None = None,
        settings: Settings | None = None,
    ):
        self.run_dir = Path(run_dir)
        self.output_dir = Path(output_dir)
        self.ground_truth_path = ground_truth_path
        self.settings = settings or Settings.get_instance()

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load default metrics
        MetricRegistry.load_default_metrics()

        # Load data
        self._load_data()

    def _load_data(self):
        """Load run results and ground truth data."""
        # Load ground truth
        if self.ground_truth_path and self.ground_truth_path.exists():
            loader = DatasetLoader(self.settings)
            self.cases = loader.load(str(self.ground_truth_path))
            self.ground_truth_df = pd.read_excel(self.ground_truth_path)
        else:
            # Try loading from default location
            default_gt = Path("data/datasets/combine_6262.xlsx")
            if default_gt.exists():
                loader = DatasetLoader(self.settings)
                self.cases = loader.load(str(default_gt))
                self.ground_truth_df = pd.read_excel(default_gt)
            else:
                self.cases = []
                self.ground_truth_df = pd.DataFrame()

        # Load model outputs
        self.model_outputs = self._load_model_outputs()

    def _load_model_outputs(self) -> dict:
        """Load model output files."""
        outputs = {}

        # Scan all model directories under run_dir
        if self.run_dir.exists():
            for model_dir in self.run_dir.iterdir():
                if model_dir.is_dir():
                    model_name = model_dir.name
                    outputs[model_name] = self._load_single_model_output(model_dir)

        return outputs

    def _load_single_model_output(self, model_dir: Path) -> dict:
        """Load single model output."""
        output = {}

        # Planner output
        planner_file = model_dir / "planner_output_flattened.xlsx"
        if planner_file.exists():
            output["planner"] = pd.read_excel(planner_file)

        # Worker output
        worker_file = model_dir / "worker_1_6262.json"
        if worker_file.exists():
            with open(worker_file) as f:
                output["worker"] = json.load(f)

        # Reporter output
        reporter_file = model_dir / "reporter_output.xlsx"
        if reporter_file.exists():
            output["reporter"] = pd.read_excel(reporter_file)

        # Tool call logs
        function_call_file = model_dir / "last_function_call_with_source.xlsx"
        if not function_call_file.exists():
            function_call_file = model_dir / "excel_1_6262.xlsx"
        if function_call_file.exists():
            output["function_calls"] = pd.read_excel(function_call_file)

        # Token usage
        token_file = model_dir / "excel_1_6262.xlsx"
        if token_file.exists():
            output["tokens"] = pd.read_excel(token_file)

        return output

    def evaluate_metric(self, metric_name: str) -> dict:
        """Execute single evaluation metric.

        Args:
            metric_name: Metric name

        Returns:
            Evaluation results dictionary
        """
        # Get metric configuration
        eval_config = self.settings.evaluation
        metric_config = getattr(eval_config, metric_name, {})

        # Get metric instance
        metric = MetricRegistry.get(metric_name, config=metric_config)
        if metric is None:
            raise ValueError(f"Unknown evaluation metric: {metric_name}")

        logger.info(f"Executing evaluation: {metric_name}")

        results = {}
        for model_name, model_output in self.model_outputs.items():
            logger.info(f"  Evaluating model: {model_name}")

            # Prepare prediction and ground truth data
            predictions = self._prepare_predictions(model_name, model_output, metric_name)
            ground_truths = self._prepare_ground_truths(metric_name)

            # Execute evaluation
            metric_results = metric.batch_compute(predictions, ground_truths)

            # Aggregate results
            summary = metric.aggregate(metric_results)

            # Aggregate by category
            by_source = metric.aggregate_by_category(metric_results, "source_file")

            results[model_name] = {
                "results": metric_results,
                "summary": summary,
                "by_source": by_source,
            }

            # Save detailed results
            df = metric.to_dataframe(metric_results)
            output_file = self.output_dir / model_name / f"{metric_name}_evaluation.csv"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(output_file, index=False, encoding="utf-8-sig")

        return results

    def _prepare_predictions(
        self,
        model_name: str,
        model_output: dict,
        metric_name: str,
    ) -> list[dict]:
        """Prepare prediction data."""
        predictions = []

        # Select data source based on metric type
        if metric_name == "tool":
            df = model_output.get("function_calls", pd.DataFrame())
            if not df.empty:
                for case_id, group in df.groupby("Case ID"):
                    predictions.append({
                        "case_id": str(case_id),
                        "tool_calls": group.to_dict("records"),
                    })

        elif metric_name == "instruction":
            df = model_output.get("planner", pd.DataFrame())
            if not df.empty:
                for _, row in df.iterrows():
                    predictions.append({
                        "case_id": str(row.get("Case ID", "")),
                        "thinking": row.get("thinking", ""),
                        "intent": row.get("intent", ""),
                        "steps": row.get("steps", ""),
                    })

        elif metric_name == "planning":
            df = model_output.get("planner", pd.DataFrame())
            if not df.empty:
                for _, row in df.iterrows():
                    predictions.append({
                        "case_id": str(row.get("Case ID", "")),
                        "steps": row.get("steps", ""),
                    })

        elif metric_name == "answer":
            df = model_output.get("reporter", pd.DataFrame())
            if not df.empty:
                for _, row in df.iterrows():
                    predictions.append({
                        "case_id": str(row.get("Case ID", "")),
                        "answer": row.get("reporter_response", ""),
                    })

        elif metric_name == "efficiency":
            df = model_output.get("tokens", pd.DataFrame())
            if not df.empty:
                for _, row in df.iterrows():
                    predictions.append({
                        "case_id": str(row.get("Case ID", "")),
                        "token_usage": row.to_dict(),
                    })

        return predictions

    def _prepare_ground_truths(self, metric_name: str) -> list[dict]:
        """Prepare ground truth data."""
        ground_truths = []

        for case in self.cases:
            gt = {
                "case_id": case.case_id,
                "source_file": case.source_file,
            }

            if case.ground_truth:
                gt["tool_list"] = case.ground_truth.tool_list
                gt["llm_class"] = case.ground_truth.llm_class
                gt["route_ans"] = case.ground_truth.route_ans
                gt["weather_description"] = case.ground_truth.weather_description
                gt["poi_result"] = case.ground_truth.poi_result

            ground_truths.append(gt)

        return ground_truths

    def aggregate_results(self, results: dict) -> dict:
        """Aggregate all evaluation results.

        Args:
            results: Evaluation results for each metric

        Returns:
            Summary results
        """
        summary = {}

        for metric_name, metric_results in results.items():
            summary[metric_name] = {}

            for model_name, model_results in metric_results.items():
                model_summary = model_results.get("summary")
                if model_summary:
                    summary[metric_name][model_name] = model_summary.average_score

        return summary

    def save_results(self, results: dict, summary: dict):
        """Save evaluation results.

        Args:
            results: Detailed results
            summary: Summary results
        """
        # Save summary table
        summary_records = []
        for metric_name, metric_summary in summary.items():
            for model_name, score in metric_summary.items():
                summary_records.append({
                    "metric": metric_name,
                    "model": model_name,
                    "score": score,
                })

        if summary_records:
            summary_df = pd.DataFrame(summary_records)
            summary_file = self.output_dir / "evaluation_summary.csv"
            summary_df.to_csv(summary_file, index=False, encoding="utf-8-sig")
            logger.info(f"Summary results saved to: {summary_file}")

        # Save complete results as JSON
        results_file = self.output_dir / "evaluation_results.json"
        with open(results_file, "w") as f:
            # Convert to serializable format
            serializable = {}
            for metric_name, metric_results in results.items():
                serializable[metric_name] = {}
                for model_name, model_results in metric_results.items():
                    serializable[metric_name][model_name] = {
                        "summary": model_results["summary"].to_dict() if model_results.get("summary") else None,
                    }
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        logger.info(f"Detailed results saved to: {results_file}")

    def run_all(self, metrics: list[str] | None = None) -> dict:
        """Run all evaluations.

        Args:
            metrics: List of metrics to run, None for all

        Returns:
            All evaluation results
        """
        if metrics is None:
            metrics = MetricRegistry.list_names()

        all_results = {}
        for metric_name in metrics:
            try:
                all_results[metric_name] = self.evaluate_metric(metric_name)
            except Exception as e:
                logger.error(f"Evaluation {metric_name} failed: {e}")
                all_results[metric_name] = {"error": str(e)}

        summary = self.aggregate_results(all_results)
        self.save_results(all_results, summary)

        return all_results
