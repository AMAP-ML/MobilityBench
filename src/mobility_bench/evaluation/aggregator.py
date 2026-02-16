"""Result aggregator."""

from pathlib import Path

import pandas as pd

from mobility_bench.config.settings import Settings


class ResultAggregator:
    """Result aggregator.

    Used for aggregating evaluation results from multiple runs and comparative analysis.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.get_instance()
        self.results_dir = Path("data/results")

    def compare_runs(
        self,
        run_ids: list[str],
        metrics: list[str],
    ) -> dict:
        """Compare results from multiple runs.

        Args:
            run_ids: List of run IDs
            metrics: List of metrics to compare

        Returns:
            Comparison results dictionary
        """
        comparison = {}

        for run_id in run_ids:
            run_results = self._load_run_results(run_id)
            comparison[run_id] = {}

            for metric in metrics:
                if metric in run_results:
                    comparison[run_id][metric] = run_results[metric]

        return comparison

    def _load_run_results(self, run_id: str) -> dict:
        """Load results from a single run."""
        eval_dir = self.results_dir / run_id / "evaluation"
        results = {}

        # Load summary
        summary_file = eval_dir / "evaluation_summary.csv"
        if summary_file.exists():
            df = pd.read_csv(summary_file)
            for _, row in df.iterrows():
                metric = row.get("metric", "")
                score = row.get("score", 0)
                results[metric] = score

        return results

    def aggregate_by_model(self, run_ids: list[str]) -> pd.DataFrame:
        """Aggregate results by model.

        Args:
            run_ids: List of run IDs

        Returns:
            Aggregated DataFrame
        """
        all_records = []

        for run_id in run_ids:
            eval_dir = self.results_dir / run_id / "evaluation"
            summary_file = eval_dir / "evaluation_summary.csv"

            if summary_file.exists():
                df = pd.read_csv(summary_file)
                df["run_id"] = run_id
                all_records.append(df)

        if all_records:
            return pd.concat(all_records, ignore_index=True)

        return pd.DataFrame()

    def aggregate_by_source(
        self,
        run_id: str,
        metric: str,
    ) -> pd.DataFrame:
        """Aggregate results by source_file.

        Args:
            run_id: Run ID
            metric: Metric name

        Returns:
            DataFrame aggregated by source_file
        """
        eval_dir = self.results_dir / run_id / "evaluation"

        # Find detailed results file for the metric
        for model_dir in eval_dir.iterdir():
            if model_dir.is_dir():
                metric_file = model_dir / f"{metric}_evaluation.csv"
                if metric_file.exists():
                    df = pd.read_csv(metric_file)
                    if "source_file" in df.columns:
                        return df.groupby("source_file").agg({
                            "score": ["mean", "std", "count"]
                        }).round(4)

        return pd.DataFrame()

    def generate_leaderboard(
        self,
        run_ids: list[str],
        primary_metric: str = "answer",
    ) -> pd.DataFrame:
        """Generate leaderboard.

        Args:
            run_ids: List of run IDs
            primary_metric: Primary sorting metric

        Returns:
            Leaderboard DataFrame
        """
        df = self.aggregate_by_model(run_ids)

        if df.empty:
            return df

        # Sort by primary metric
        if primary_metric in df["metric"].values:
            primary_scores = df[df["metric"] == primary_metric][["model", "score"]]
            primary_scores = primary_scores.rename(columns={"score": primary_metric})

            # Merge other metrics
            pivot = df.pivot(index="model", columns="metric", values="score")
            leaderboard = pivot.sort_values(by=primary_metric, ascending=False)

            return leaderboard

        return df.pivot(index="model", columns="metric", values="score")
