"""Report generator."""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from mobility_bench.config.settings import Settings


class ReportGenerator:
    """Report generator.

    Supports generating Markdown, HTML and Excel format evaluation reports.
    """

    def __init__(
        self,
        run_dir: Path,
        settings: Settings | None = None,
        template: str | None = None,
    ):
        self.run_dir = Path(run_dir)
        self.settings = settings or Settings.get_instance()
        self.template = template

    def generate(
        self,
        format: str = "markdown",
        output_path: Path | None = None,
        include_traces: bool = False,
        compare_runs: list[str] | None = None,
    ) -> Path:
        """Generate report.

        Args:
            format: Output format (markdown/html/excel)
            output_path: Output path
            include_traces: Whether to include detailed traces
            compare_runs: List of run IDs to compare

        Returns:
            Report file path
        """
        # Load evaluation results
        eval_dir = self.run_dir / "evaluation"
        if not eval_dir.exists():
            raise FileNotFoundError(f"Evaluation results directory not found: {eval_dir}")

        # Load summary data
        summary_file = eval_dir / "evaluation_summary.csv"
        if summary_file.exists():
            summary_df = pd.read_csv(summary_file)
        else:
            summary_df = pd.DataFrame()

        # Load detailed results
        results_file = eval_dir / "evaluation_results.json"
        if results_file.exists():
            with open(results_file) as f:
                results = json.load(f)
        else:
            results = {}

        # Generate report based on format
        if format == "markdown":
            content = self._generate_markdown(summary_df, results, include_traces, compare_runs)
            ext = "md"
        elif format == "html":
            content = self._generate_html(summary_df, results, include_traces, compare_runs)
            ext = "html"
        elif format == "excel":
            return self._generate_excel(summary_df, results, output_path, compare_runs)
        else:
            raise ValueError(f"Unsupported format: {format}")

        # Write file
        if output_path is None:
            output_path = self.run_dir / "reports" / f"report.{ext}"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    def _generate_markdown(
        self,
        summary_df: pd.DataFrame,
        results: dict,
        include_traces: bool,
        compare_runs: list[str] | None,
    ) -> str:
        """Generate Markdown report."""
        lines = []

        # Title
        lines.append("# MobilityBench Evaluation Report")
        lines.append("")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Run directory: `{self.run_dir}`")
        lines.append("")

        # Overall summary
        lines.append("## Evaluation Results Summary")
        lines.append("")

        if not summary_df.empty:
            # Pivot by model and metric
            pivot = summary_df.pivot(index="model", columns="metric", values="score")
            lines.append(pivot.to_markdown())
            lines.append("")

        # Details for each metric
        for metric_name, metric_results in results.items():
            lines.append(f"## {metric_name} Evaluation Details")
            lines.append("")

            for model_name, model_results in metric_results.items():
                lines.append(f"### {model_name}")
                lines.append("")

                summary = model_results.get("summary", {})
                if summary:
                    lines.append(f"- Average score: {summary.get('average_score', 'N/A'):.4f}")
                    lines.append(f"- Total cases: {summary.get('total_cases', 0)}")
                    lines.append(f"- Successful cases: {summary.get('successful_cases', 0)}")
                    lines.append(f"- Failed cases: {summary.get('failed_cases', 0)}")
                    lines.append("")

        # Comparison analysis
        if compare_runs:
            lines.append("## Model Comparison Analysis")
            lines.append("")
            lines.append("Compared run IDs:")
            for run_id in compare_runs:
                lines.append(f"- {run_id}")
            lines.append("")

        return "\n".join(lines)

    def _generate_html(
        self,
        summary_df: pd.DataFrame,
        results: dict,
        include_traces: bool,
        compare_runs: list[str] | None,
    ) -> str:
        """Generate HTML report."""
        html_parts = []

        # HTML header
        html_parts.append("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>MobilityBench Evaluation Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        h2 { color: #666; border-bottom: 1px solid #ddd; padding-bottom: 10px; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
        th { background-color: #4CAF50; color: white; }
        tr:nth-child(even) { background-color: #f2f2f2; }
        .metric-card { background: #f9f9f9; padding: 20px; margin: 10px 0; border-radius: 5px; }
        .score { font-size: 24px; font-weight: bold; color: #4CAF50; }
    </style>
</head>
<body>
""")

        # Title
        html_parts.append(f"""
    <h1>MobilityBench Evaluation Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    <p>Run directory: <code>{self.run_dir}</code></p>
""")

        # Summary table
        if not summary_df.empty:
            html_parts.append("<h2>Evaluation Results Summary</h2>")
            pivot = summary_df.pivot(index="model", columns="metric", values="score")
            html_parts.append(pivot.to_html(classes="summary-table"))

        # Details for each metric
        for metric_name, metric_results in results.items():
            html_parts.append(f"<h2>{metric_name} Evaluation Details</h2>")

            for model_name, model_results in metric_results.items():
                summary = model_results.get("summary", {})
                html_parts.append(f"""
    <div class="metric-card">
        <h3>{model_name}</h3>
        <p class="score">{summary.get('average_score', 0):.4f}</p>
        <p>Total cases: {summary.get('total_cases', 0)} |
           Successful: {summary.get('successful_cases', 0)} |
           Failed: {summary.get('failed_cases', 0)}</p>
    </div>
""")

        # HTML footer
        html_parts.append("""
</body>
</html>
""")

        return "\n".join(html_parts)

    def _generate_excel(
        self,
        summary_df: pd.DataFrame,
        results: dict,
        output_path: Path | None,
        compare_runs: list[str] | None,
    ) -> Path:
        """Generate Excel report."""
        if output_path is None:
            output_path = self.run_dir / "reports" / "report.xlsx"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # Summary table
            if not summary_df.empty:
                summary_df.to_excel(writer, sheet_name="Summary", index=False)

                # Pivot table
                pivot = summary_df.pivot(index="model", columns="metric", values="score")
                pivot.to_excel(writer, sheet_name="Pivot")

            # Details for each metric
            for metric_name, metric_results in results.items():
                records = []
                for model_name, model_results in metric_results.items():
                    summary = model_results.get("summary", {})
                    records.append({
                        "model": model_name,
                        "average_score": summary.get("average_score", 0),
                        "total_cases": summary.get("total_cases", 0),
                        "successful_cases": summary.get("successful_cases", 0),
                        "failed_cases": summary.get("failed_cases", 0),
                    })

                if records:
                    df = pd.DataFrame(records)
                    sheet_name = metric_name[:31]  # Excel sheet name limit
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

        return output_path


class ComparisonReportGenerator:
    """Comparison report generator."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.get_instance()

    def generate_comparison(
        self,
        run_ids: list[str],
        metrics: list[str],
        output_path: Path | None = None,
        format: str = "markdown",
    ) -> Path:
        """Generate comparison report.

        Args:
            run_ids: List of run IDs to compare
            metrics: List of metrics to compare
            output_path: Output path
            format: Output format

        Returns:
            Report file path
        """
        # Collect results from each run
        all_results = {}
        for run_id in run_ids:
            run_dir = Path("data/results") / run_id / "evaluation"
            if run_dir.exists():
                summary_file = run_dir / "evaluation_summary.csv"
                if summary_file.exists():
                    df = pd.read_csv(summary_file)
                    all_results[run_id] = df

        if not all_results:
            raise ValueError("No evaluation results found")

        # Merge results
        combined = []
        for run_id, df in all_results.items():
            df["run_id"] = run_id
            combined.append(df)

        combined_df = pd.concat(combined, ignore_index=True)

        # Generate comparison report
        if format == "markdown":
            return self._generate_markdown_comparison(combined_df, output_path)
        elif format == "excel":
            return self._generate_excel_comparison(combined_df, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _generate_markdown_comparison(
        self,
        df: pd.DataFrame,
        output_path: Path | None,
    ) -> Path:
        """Generate Markdown comparison report."""
        lines = []
        lines.append("# MobilityBench Model Comparison Report")
        lines.append("")
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Pivot table
        pivot = df.pivot_table(
            index=["model", "run_id"],
            columns="metric",
            values="score",
            aggfunc="mean",
        )
        lines.append(pivot.to_markdown())

        if output_path is None:
            output_path = Path("data/results/comparison_report.md")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        return output_path

    def _generate_excel_comparison(
        self,
        df: pd.DataFrame,
        output_path: Path | None,
    ) -> Path:
        """Generate Excel comparison report."""
        if output_path is None:
            output_path = Path("data/results/comparison_report.xlsx")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Raw", index=False)

            pivot = df.pivot_table(
                index=["model", "run_id"],
                columns="metric",
                values="score",
                aggfunc="mean",
            )
            pivot.to_excel(writer, sheet_name="Comparison")

        return output_path
