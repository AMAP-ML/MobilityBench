"""
Run command implementation for MobilityBench CLI.

This module handles agent batch running with support for
multiple models, parallel execution, and checkpoint resumption.
"""

import time
import uuid
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

console = Console()


def run_benchmark(
    model: str | None = None,
    models: str | None = None,
    dataset: str = "mobility_6262",
    framework: str = "plan_and_execute",
    config: Path | None = None,
    output_dir: Path | None = None,
    parallel: int = 1,
    sandbox: bool = True,
    resume: str | None = None,
    dry_run: bool = False,
) -> str:
    """
    Core logic for running agent evaluation.

    Args:
        model: Single model name
        models: Multiple model names, comma-separated
        dataset: Dataset name or path
        framework: Agent framework (plan_and_execute or react)
        config: Configuration file path
        output_dir: Output directory
        parallel: Parallelism level
        sandbox: Whether to use sandbox tools
        resume: Run ID to resume from
        dry_run: Whether to only validate without executing

    Returns:
        Run ID
    """
    import typer

    from mobility_bench.config.settings import Settings
    from mobility_bench.dataset.loader import DatasetLoader
    from mobility_bench.runner.batch import BatchRunner

    # Validate framework
    valid_frameworks = ["plan_and_execute", "react"]
    if framework not in valid_frameworks:
        console.print(f"[red]Error: Invalid framework '{framework}'. Must be one of: {', '.join(valid_frameworks)}[/red]")
        raise typer.Exit(1)

    # Parse model list
    model_list = []
    if model:
        model_list.append(model)
    if models:
        model_list.extend([m.strip() for m in models.split(",")])

    if not model_list:
        console.print("[red]Error: Must specify at least one model (--model or --models)[/red]")
        raise typer.Exit(1)

    # Generate or resume run ID
    run_id = resume or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

    # Set output directory
    if output_dir is None:
        output_dir = Path("data/results") / run_id
    output_dir = Path(output_dir)

    console.print("\n[bold cyan]MobilityBench Run Configuration[/bold cyan]")
    console.print(f"  Run ID: [green]{run_id}[/green]")
    console.print(f"  Models: [yellow]{', '.join(model_list)}[/yellow]")
    console.print(f"  Dataset: [yellow]{dataset}[/yellow]")
    console.print(f"  Framework: [yellow]{framework}[/yellow]")
    console.print(f"  Parallel: [yellow]{parallel}[/yellow]")
    console.print(f"  Tool Mode: [yellow]{'Sandbox' if sandbox else 'Live'}[/yellow]")
    console.print(f"  Output Dir: [yellow]{output_dir}[/yellow]")

    if dry_run:
        console.print("\n[yellow]--dry-run mode: Validating config only, not executing[/yellow]")
        return run_id

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load configuration
    settings = Settings.load(config)

    # Save run metadata for evaluation to reference later
    import json
    metadata = {
        "run_id": run_id,
        "models": model_list,
        "dataset": dataset,
        "framework": framework,
        "sandbox": sandbox,
    }
    with open(output_dir / "run_metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # Load dataset
    console.print("\n[bold]Loading dataset...[/bold]")
    loader = DatasetLoader(settings)
    cases = loader.load(dataset)
    console.print(f"  Loaded [green]{len(cases)}[/green] test cases")

    # Create runner
    runner = BatchRunner(
        models=model_list,
        framework=framework,
        settings=settings,
        output_dir=output_dir,
        parallel=parallel,
        sandbox=sandbox,
    )

    # Execute run
    console.print("\n[bold]Starting run...[/bold]")

    # Track per-model statistics
    model_stats: dict[str, dict] = {}
    model_tasks: dict[str, int] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:

        def _progress_callback(event, model_name, case_id, current, total, status):
            if event == "start_model":
                task_id = progress.add_task(
                    f"[cyan]{model_name}[/cyan]  Preparing...",
                    total=total,
                )
                model_tasks[model_name] = task_id
                model_stats[model_name] = {
                    "total": total,
                    "success": 0,
                    "failed": 0,
                    "start_time": time.time(),
                }
            elif event == "case_complete":
                task_id = model_tasks.get(model_name)
                stats = model_stats.get(model_name, {})
                if status == "success":
                    stats["success"] = stats.get("success", 0) + 1
                else:
                    stats["failed"] = stats.get("failed", 0) + 1
                if task_id is not None:
                    progress.update(
                        task_id,
                        advance=1,
                        description=(
                            f"[cyan]{model_name}[/cyan]  "
                            f"[green]{stats.get('success', 0)}[/green]"
                            f"[red]{'/' + str(stats.get('failed', 0)) if stats.get('failed') else ''}[/red]"
                            f"  {case_id}"
                        ),
                    )

        runner.run(cases, resume_from=resume, progress_callback=_progress_callback)

    # Print summary table
    if model_stats:
        console.print()
        table = Table(title="Run Summary", show_header=True, header_style="bold magenta")
        table.add_column("Model", style="cyan")
        table.add_column("Total", justify="right")
        table.add_column("Success", justify="right", style="green")
        table.add_column("Failed", justify="right", style="red")
        table.add_column("Time", justify="right")

        for model_name, stats in model_stats.items():
            elapsed = time.time() - stats.get("start_time", time.time())
            mins, secs = divmod(int(elapsed), 60)
            hours, mins = divmod(mins, 60)
            time_str = f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins}:{secs:02d}"
            table.add_row(
                model_name,
                str(stats["total"]),
                str(stats["success"]),
                str(stats["failed"]),
                time_str,
            )
        console.print(table)

    # Output summary
    console.print("\n[bold green]Run completed![/bold green]")
    console.print(f"  Results saved to: [cyan]{output_dir}[/cyan]")
    console.print(f"  Run ID: [cyan]{run_id}[/cyan]")
    console.print("\nTo evaluate, run:")
    console.print(f"  [dim]mbench eval --run-id {run_id}[/dim]")

    return run_id
