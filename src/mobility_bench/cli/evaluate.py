"""
Evaluate command implementation for MobilityBench CLI.

This module handles evaluation execution with support for
multiple metrics and model comparison.
"""

from pathlib import Path

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

console = Console()


def run_evaluation(
    run_id: str,
    metrics: str = "all",
    ground_truth: Path | None = None,
    output_dir: Path | None = None,
    compare: str | None = None,
) -> dict:
    """
    Core logic for executing evaluation.

    Args:
        run_id: Run ID
        metrics: Metrics to evaluate, comma-separated or "all"
        ground_truth: Ground truth file path
        output_dir: Evaluation output directory
        compare: Run IDs to compare, comma-separated

    Returns:
        Evaluation results dictionary
    """
    import typer

    from mobility_bench.config.settings import Settings
    from mobility_bench.evaluation.runner import EvaluationRunner

    # Parse metric list
    if metrics.lower() == "all":
        metric_list = ["tool", "instruction", "planning", "answer", "efficiency"]
    else:
        metric_list = [m.strip() for m in metrics.split(",")]

    # Set output directory
    run_dir = Path("data/results") / run_id
    if output_dir is None:
        output_dir = run_dir / "evaluation"
    output_dir = Path(output_dir)

    console.print("\n[bold cyan]MobilityBench Evaluation Configuration[/bold cyan]")
    console.print(f"  Run ID: [green]{run_id}[/green]")
    console.print(f"  Metrics: [yellow]{', '.join(metric_list)}[/yellow]")
    console.print(f"  Output Dir: [yellow]{output_dir}[/yellow]")

    # Check if run directory exists
    if not run_dir.exists():
        console.print(f"[red]Error: Run directory does not exist: {run_dir}[/red]")
        raise typer.Exit(1)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load configuration
    settings = Settings.load()

    # Create evaluation runner
    runner = EvaluationRunner(
        run_dir=run_dir,
        output_dir=output_dir,
        ground_truth_path=ground_truth,
        settings=settings,
    )

    # Execute evaluation
    results = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Evaluating...", total=len(metric_list))

        for metric_name in metric_list:
            progress.update(task, description=f"Evaluating {metric_name}...")
            try:
                metric_result = runner.evaluate_metric(metric_name)
                results[metric_name] = metric_result
                progress.advance(task)
            except Exception as e:
                console.print(f"[yellow]Warning: {metric_name} evaluation failed: {e}[/yellow]")
                progress.advance(task)

    # Aggregate results
    summary = runner.aggregate_results(results)

    # Display summary
    _display_results_summary(results, summary)

    # Save results
    runner.save_results(results, summary)

    console.print("\n[bold green]Evaluation completed![/bold green]")
    console.print(f"  Results saved to: [cyan]{output_dir}[/cyan]")
    console.print("\nTo generate report, run:")
    console.print(f"  [dim]mbench report --run-id {run_id}[/dim]")

    # Run comparison if requested
    if compare:
        compare_ids = [c.strip() for c in compare.split(",")]
        _run_comparison(run_id, compare_ids, metric_list, settings)

    return results


def _display_results_summary(results: dict, summary: dict):
    """Display evaluation results summary with sub-dimensions."""
    overall = summary.get("overall", {})
    by_intent_family = summary.get("by_intent_family", {})

    # Collect all model names
    model_names = set()
    for metric_models in overall.values():
        if isinstance(metric_models, dict):
            model_names.update(metric_models.keys())
    model_names = sorted(model_names)

    # --- Overall summary table ---
    console.print("\n[bold]Overall Evaluation Results[/bold]")
    _print_sub_dim_table(results, overall, model_names)

    # --- Per intent_family tables ---
    if by_intent_family:
        console.print("\n[bold]Evaluation Results by Intent Family[/bold]")

        for family_name in sorted(by_intent_family.keys()):
            family_metrics = by_intent_family[family_name]
            console.print(f"\n[bold cyan]  [{family_name}][/bold cyan]")

            _print_sub_dim_table(
                results, family_metrics, model_names,
                get_cases_fn=lambda mr, mn: _get_family_cases(mr, mn, family_name),
            )


def _get_family_cases(metric_result: dict, metric_name: str, family_name: str) -> str:
    """Get total_cases for a specific intent_family."""
    mr = metric_result.get(metric_name, {})
    for model_result in mr.values():
        if isinstance(model_result, dict):
            by_fam = model_result.get("by_intent_family", {})
            fam_summary = by_fam.get(family_name)
            if fam_summary:
                return str(fam_summary.total_cases)
    return "N/A"


def _format_value(value) -> str:
    """Format a numeric value for display."""
    if isinstance(value, float):
        return f"{value:.0f}" if value > 100 else f"{value:.4f}"
    elif isinstance(value, int):
        return str(value)
    return str(value)


def _print_sub_dim_table(
    results: dict,
    metric_summary: dict,
    model_names: list[str],
    get_cases_fn=None,
):
    """Print a sub-dimension table for given metric summary data."""
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Sub-dimension", style="white")
    for model_name in model_names:
        table.add_column(model_name, justify="right")
    table.add_column("Cases", justify="right", style="dim")

    for metric_name, metric_models in metric_summary.items():
        if not isinstance(metric_models, dict):
            continue

        # Get total_cases
        if get_cases_fn:
            total_cases = get_cases_fn(results, metric_name)
        else:
            total_cases = "N/A"
            metric_result = results.get(metric_name, {})
            for model_result in metric_result.values():
                if isinstance(model_result, dict) and "summary" in model_result:
                    total_cases = str(model_result["summary"].total_cases)
                    break

        # Collect sub-dimensions: handle both direct dict and nested {sub_scores, total_cases}
        all_sub_dims = []
        for model_data in metric_models.values():
            sub_scores = model_data.get("sub_scores", model_data) if isinstance(model_data, dict) else {}
            if isinstance(sub_scores, dict):
                for dim in sub_scores:
                    if dim not in all_sub_dims and dim != "total_cases":
                        all_sub_dims.append(dim)

        for i, sub_dim in enumerate(all_sub_dims):
            row_metric = metric_name if i == 0 else ""
            row = [row_metric, sub_dim]
            for model_name in model_names:
                model_data = metric_models.get(model_name, {})
                sub_scores = model_data.get("sub_scores", model_data) if isinstance(model_data, dict) else {}
                value = sub_scores.get(sub_dim, "N/A") if isinstance(sub_scores, dict) else "N/A"
                row.append(_format_value(value))
            row.append(total_cases if i == 0 else "")
            table.add_row(*row)

        if all_sub_dims:
            table.add_row(*[""] * (3 + len(model_names)), end_section=True)

    console.print(table)


def _run_comparison(run_id: str, compare_ids: list, metrics: list, settings):
    """Run model comparison."""
    from mobility_bench.evaluation.aggregator import ResultAggregator

    console.print(f"\n[bold]Model Comparison: {run_id} vs {', '.join(compare_ids)}[/bold]")

    aggregator = ResultAggregator(settings)
    comparison = aggregator.compare_runs([run_id] + compare_ids, metrics)

    # Display comparison table
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    for rid in [run_id] + compare_ids:
        table.add_column(rid, justify="right")

    for metric in metrics:
        row = [metric]
        for rid in [run_id] + compare_ids:
            score = comparison.get(rid, {}).get(metric, "N/A")
            if isinstance(score, float):
                score = f"{score:.4f}"
            row.append(str(score))
        table.add_row(*row)

    console.print(table)
