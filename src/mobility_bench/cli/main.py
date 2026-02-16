"""
MobilityBench CLI main entry point.

This module provides the main CLI interface using Typer,
supporting commands for running agents, evaluation, and reporting.
"""

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(
    name="mb",
    help="MobilityBench - Mobility Agent Evaluation Framework",
    add_completion=False,
    pretty_exceptions_enable=True,
)
console = Console()


@app.command()
def run(
    model: str | None = typer.Option(
        None, "--model", "-m", help="Single model name"
    ),
    models: str | None = typer.Option(
        None, "--models", help="Multiple models, comma-separated"
    ),
    dataset: str = typer.Option(
        "mobility_6262", "--dataset", "-d", help="Dataset name or path"
    ),
    framework: str = typer.Option(
        "plan_and_execute", "--framework", "-f", help="Agent framework (plan_and_execute or react)"
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help="Configuration file path"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Output directory"
    ),
    parallel: int = typer.Option(1, "--parallel", "-p", help="Parallelism level"),
    sandbox: bool = typer.Option(True, "--sandbox/--live", help="Use sandbox/live tools"),
    resume: str | None = typer.Option(None, "--resume", help="Resume from run ID"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate config only"),
):
    """Run agent evaluation."""
    from mobility_bench.cli.run import run_benchmark

    run_benchmark(
        model=model,
        models=models,
        dataset=dataset,
        framework=framework,
        config=config,
        output_dir=output_dir,
        parallel=parallel,
        sandbox=sandbox,
        resume=resume,
        dry_run=dry_run,
    )


@app.command()
def eval(
    run_id: str = typer.Option(..., "--run-id", "-r", help="Run ID"),
    metrics: str = typer.Option(
        "all", "--metrics", "-m", help="Metrics (tool/instruction/planning/answer/efficiency/all)"
    ),
    ground_truth: Path | None = typer.Option(
        None, "--ground-truth", help="Ground truth file path"
    ),
    output_dir: Path | None = typer.Option(
        None, "--output-dir", "-o", help="Evaluation output directory"
    ),
    compare: str | None = typer.Option(
        None, "--compare", help="Run IDs to compare, comma-separated"
    ),
):
    """Execute evaluation."""
    from mobility_bench.cli.evaluate import run_evaluation

    run_evaluation(
        run_id=run_id,
        metrics=metrics,
        ground_truth=ground_truth,
        output_dir=output_dir,
        compare=compare,
    )


@app.command()
def report(
    run_id: str = typer.Option(..., "--run-id", "-r", help="Run ID"),
    format: str = typer.Option(
        "markdown", "--format", "-f", help="Output format (markdown/html/excel)"
    ),
    template: str | None = typer.Option(None, "--template", help="Report template name"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path"),
    include_traces: bool = typer.Option(
        False, "--include-traces", help="Include detailed traces"
    ),
    compare: str | None = typer.Option(
        None, "--compare", help="Run IDs to compare, comma-separated"
    ),
):
    """Generate evaluation report."""
    from mobility_bench.cli.report import generate_report

    generate_report(
        run_id=run_id,
        format=format,
        template=template,
        output=output,
        include_traces=include_traces,
        compare=compare,
    )


@app.command()
def config(
    action: str = typer.Argument(
        "show", help="Action type (show/validate/init)"
    ),
    path: Path | None = typer.Argument(None, help="Configuration file path"),
    template: str | None = typer.Option(
        None, "--template", help="Template name (for init)"
    ),
):
    """Configuration management."""
    from mobility_bench.cli.config import manage_config

    manage_config(action=action, path=path, template=template)


@app.command()
def version():
    """Show version information."""
    from mobility_bench import __version__

    console.print(f"[bold green]MobilityBench[/bold green] v{__version__}")


if __name__ == "__main__":
    app()
