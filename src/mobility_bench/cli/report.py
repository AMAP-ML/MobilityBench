"""
Report command implementation for MobilityBench CLI.

This module handles report generation in multiple formats
(Markdown, HTML, Excel) with comparison support.
"""

from pathlib import Path

from rich.console import Console

console = Console()


def generate_report(
    run_id: str,
    format: str = "markdown",
    template: str | None = None,
    output: Path | None = None,
    include_traces: bool = False,
    compare: str | None = None,
) -> Path:
    """
    Core logic for generating evaluation report.

    Args:
        run_id: Run ID
        format: Output format (markdown/html/excel)
        template: Report template name
        output: Output file path
        include_traces: Whether to include detailed traces
        compare: Run IDs to compare, comma-separated

    Returns:
        Report file path
    """
    import typer

    from mobility_bench.config.settings import Settings
    from mobility_bench.reporting.generator import ReportGenerator

    # Set default output path
    run_dir = Path("data/results") / run_id
    if output is None:
        ext = {"markdown": "md", "html": "html", "excel": "xlsx"}.get(format, "md")
        output = run_dir / "reports" / f"report.{ext}"
    output = Path(output)

    console.print("\n[bold cyan]MobilityBench Report Generation[/bold cyan]")
    console.print(f"  Run ID: [green]{run_id}[/green]")
    console.print(f"  Format: [yellow]{format}[/yellow]")
    console.print(f"  Output: [yellow]{output}[/yellow]")

    # Check run directory
    if not run_dir.exists():
        console.print(f"[red]Error: Run directory does not exist: {run_dir}[/red]")
        raise typer.Exit(1)

    # Create output directory
    output.parent.mkdir(parents=True, exist_ok=True)

    # Load configuration
    settings = Settings.load()

    # Create report generator
    generator = ReportGenerator(
        run_dir=run_dir,
        settings=settings,
        template=template,
    )

    # Handle comparison mode
    compare_ids = None
    if compare:
        compare_ids = [c.strip() for c in compare.split(",")]
        console.print(f"  Comparing: [yellow]{', '.join(compare_ids)}[/yellow]")

    # Generate report
    console.print("\n[bold]Generating report...[/bold]")
    report_path = generator.generate(
        format=format,
        output_path=output,
        include_traces=include_traces,
        compare_runs=compare_ids,
    )

    console.print("\n[bold green]Report generated![/bold green]")
    console.print(f"  Report path: [cyan]{report_path}[/cyan]")

    return report_path
