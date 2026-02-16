"""
Config command implementation for MobilityBench CLI.

This module handles configuration management including
viewing, validating, and initializing configurations.
"""

from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax

console = Console()


def manage_config(
    action: str = "show",
    path: Path | None = None,
    template: str | None = None,
):
    """
    Core logic for configuration management.

    Args:
        action: Action type (show/validate/init)
        path: Configuration file path
        template: Template name
    """
    import typer

    if action == "show":
        _show_config(path)
    elif action == "validate":
        _validate_config(path)
    elif action == "init":
        _init_config(template, path)
    else:
        console.print(f"[red]Unknown action: {action}[/red]")
        console.print("Available actions: show, validate, init")
        raise typer.Exit(1)


def _show_config(path: Path | None = None):
    """Display current configuration."""
    import typer

    from mobility_bench.config.settings import Settings

    console.print("\n[bold cyan]Current Configuration[/bold cyan]")

    if path:
        # Display specified config file
        if not path.exists():
            console.print(f"[red]Config file not found: {path}[/red]")
            raise typer.Exit(1)

        with open(path) as f:
            content = f.read()

        syntax = Syntax(content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)
    else:
        # Display default configuration
        settings = Settings.load()
        config_dict = settings.to_dict()

        console.print("\n[bold]Model Configuration:[/bold]")
        for name, cfg in config_dict.get("models", {}).items():
            console.print(f"  [cyan]{name}[/cyan]: {cfg.get('provider', 'unknown')}")

        console.print("\n[bold]Dataset Configuration:[/bold]")
        for name, cfg in config_dict.get("datasets", {}).items():
            console.print(f"  [cyan]{name}[/cyan]: {cfg.get('path', 'unknown')}")

        console.print("\n[bold]Evaluation Configuration:[/bold]")
        eval_cfg = config_dict.get("evaluation", {})
        metrics = eval_cfg.get("metrics", [])
        console.print(f"  Metrics: {', '.join(metrics)}")


def _validate_config(path: Path | None = None):
    """Validate configuration file."""
    import typer

    from mobility_bench.config.settings import Settings

    console.print("\n[bold cyan]Validating Configuration[/bold cyan]")

    if path is None:
        console.print("[red]Please specify config file path[/red]")
        raise typer.Exit(1)

    if not path.exists():
        console.print(f"[red]Config file not found: {path}[/red]")
        raise typer.Exit(1)

    try:
        settings = Settings.load(path)
        errors = settings.validate()

        if errors:
            console.print("[red]Configuration validation failed:[/red]")
            for error in errors:
                console.print(f"  - {error}")
            raise typer.Exit(1)
        else:
            console.print("[green]Configuration validation passed![/green]")
    except Exception as e:
        console.print(f"[red]Configuration parsing failed: {e}[/red]")
        raise typer.Exit(1)


def _init_config(template: str | None = None, output: Path | None = None):
    """Initialize configuration file."""
    templates = {
        "batch_run": _get_batch_run_template(),
        "single_model": _get_single_model_template(),
        "evaluation": _get_evaluation_template(),
    }

    if template is None:
        console.print("\n[bold]Available Templates:[/bold]")
        for name, desc in [
            ("batch_run", "Multi-model batch run configuration"),
            ("single_model", "Single model run configuration"),
            ("evaluation", "Evaluation configuration"),
        ]:
            console.print(f"  [cyan]{name}[/cyan]: {desc}")
        console.print("\nUse --template <name> to select a template")
        return

    if template not in templates:
        console.print(f"[red]Unknown template: {template}[/red]")
        raise typer.Exit(1)

    content = templates[template]

    if output:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            f.write(content)
        console.print(f"[green]Config file created: {output}[/green]")
    else:
        syntax = Syntax(content, "yaml", theme="monokai", line_numbers=True)
        console.print(syntax)


def _get_batch_run_template() -> str:
    """Batch run configuration template."""
    return """# MobilityBench Batch Run Configuration
run:
  name: "benchmark_v1"
  models:
    - gpt4.1
    - claude-opus-4-5
    - qwen3-235b
  dataset: mobility_6262
  parallel: 4
  sandbox: true

evaluation:
  metrics:
    - tool
    - instruction
    - planning
    - answer
    - efficiency
  ground_truth: data/datasets/combine_6262.xlsx

output:
  dir: data/results
  formats:
    - markdown
    - excel
"""


def _get_single_model_template() -> str:
    """Single model run configuration template."""
    return """# MobilityBench Single Model Configuration
run:
  name: "single_model_test"
  models:
    - gpt4.1
  dataset: mobility_6262
  parallel: 1
  sandbox: true

output:
  dir: data/results
"""


def _get_evaluation_template() -> str:
    """Evaluation configuration template."""
    return """# MobilityBench Evaluation Configuration
evaluation:
  metrics:
    - tool
    - instruction
    - planning
    - answer
    - efficiency

  # Tool call evaluation config
  tool:
    check_min:
      query_poi: [keywords]
      driving_route: [origin, destination]
      weather_query: [city]

  # Instruction understanding config
  instruction:
    similarity_threshold: 0.7

  # Planning evaluation config
  planning:
    alpha: 0.8  # DEC recall weight
    beta: 0.2   # DEC precision weight
"""


import typer
