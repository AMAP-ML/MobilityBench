"""
Run command implementation for MobilityBench CLI.

This module handles agent batch running with support for
multiple models, parallel execution, and checkpoint resumption.
"""

import uuid
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

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
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Running {len(model_list)} models...", total=None)
        runner.run(cases, resume_from=resume)
        progress.update(task, completed=True)

    # Output summary
    console.print("\n[bold green]Run completed![/bold green]")
    console.print(f"  Results saved to: [cyan]{output_dir}[/cyan]")
    console.print(f"  Run ID: [cyan]{run_id}[/cyan]")
    console.print("\nTo evaluate, run:")
    console.print(f"  [dim]mbench eval --run-id {run_id}[/dim]")

    return run_id
