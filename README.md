# MobilityBench

A comprehensive evaluation framework for Mobility AI Agents, designed to benchmark LLM-based agents on real-world travel and navigation tasks.

## Overview

MobilityBench provides a standardized benchmark for evaluating AI agents that handle mobility-related tasks such as route planning, POI queries, weather information, and traffic status. The framework supports:

- **Multi-model evaluation**: Test multiple LLM models (OpenAI, Anthropic, Google, Qwen) in parallel
- **Comprehensive metrics**: 5 evaluation dimensions covering tool usage, instruction understanding, planning quality, answer accuracy, and efficiency
- **Sandbox mode**: Offline evaluation using pre-cached API responses for reproducible results
- **Flexible configuration**: YAML-based configuration for models, datasets, and evaluation parameters

## Architecture

MobilityBench supports two agent frameworks powered by LangGraph:

### Plan-and-Execute Framework (Default)

A **Planner-Worker-Reporter** architecture for structured task execution:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Planner   │────▶│   Worker    │────▶│  Reporter   │
│  (Planning) │◀────│ (Execution) │     │  (Summary)  │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                    ┌──────┴──────┐
                    │  Tool Kit   │
                    │ (Map APIs)  │
                    └─────────────┘
```

- **Planner**: Analyzes user requirements, creates structured plans, dynamically adjusts based on results
- **Worker**: Executes tool calls based on the plan, supports parallel task execution
- **Reporter**: Generates comprehensive natural language reports from execution results

### ReAct Framework

A **Reasoning-Action-Observation** loop for iterative problem solving:

```
┌─────────────────────────────────────────────┐
│                                             │
│  ┌──────────┐   ┌──────────┐   ┌─────────┐ │
│  │ Reasoning│──▶│  Action  │──▶│Observat.│ │
│  │ (Think)  │   │(Tool Call)│  │(Result) │ │
│  └──────────┘   └──────────┘   └────┬────┘ │
│       ▲                             │      │
│       └─────────────────────────────┘      │
│                                             │
└─────────────────────────────────────────────┘
```

- **Reasoning**: Analyzes current state and decides next action
- **Action**: Executes tool call or finishes task
- **Observation**: Processes tool results and feeds back to reasoning

## Installation

### Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

### Quick Install

```bash
# Clone the repository
git clone https://github.com/your-org/mobility-bench.git
cd mobility-bench

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .

# Install with evaluation dependencies
uv sync --extra eval
# or
pip install -e ".[eval]"
```

## Quick Start

### 1. Configure Environment

Create a `.env` file with your LLM API credentials:

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key
```

### 2. Run Benchmark

```bash
# Run benchmark with default settings (plan_and_execute framework)
mbench run --model gpt4.1 --dataset data/dataset/test01.xlsx

# Run with ReAct framework
mbench run --model gpt4.1 --framework react

# Run multiple models in parallel
mbench run --model gpt4.1 --model claude-opus-4-5 --workers 4

# Enable sandbox mode (offline evaluation)
mbench run --model gpt4.1 --sandbox

# Compare frameworks
mbench run --model gpt4.1 --framework plan_and_execute --output-dir results/pae
mbench run --model gpt4.1 --framework react --output-dir results/react
```

### 3. Evaluate Results

```bash
# Evaluate a single run
mbench eval --run-id run_20260215_120000

# Evaluate with specific metrics
mbench eval --run-id run_20260215_120000 --metrics tool,answer,planning
```

### 4. Generate Reports

```bash
# Generate markdown report
mbench report --run-id run_20260215_120000

# Generate HTML report
mbench report --run-id run_20260215_120000 --format html

# Compare multiple runs
mbench report --run-id run_001 --run-id run_002 --compare
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `mbench run` | Run agent benchmark on dataset |
| `mbench eval` | Evaluate agent run results |
| `mbench report` | Generate evaluation reports |
| `mbench config` | Manage configuration files |
| `mbench version` | Show version information |

### Run Command Options

| Option | Description | Default |
|--------|-------------|---------|
| `--model, -m` | Model name to use | - |
| `--models` | Multiple models (comma-separated) | - |
| `--dataset, -d` | Dataset name or path | `mobility_6262` |
| `--framework, -f` | Agent framework (`plan_and_execute` or `react`) | `plan_and_execute` |
| `--config, -c` | Configuration file path | - |
| `--output-dir, -o` | Output directory | - |
| `--parallel, -p` | Parallelism level | `1` |
| `--sandbox/--live` | Use sandbox or live tools | `--sandbox` |
| `--resume` | Resume from run ID | - |
| `--dry-run` | Validate config only | `false` |

### Examples

```bash
# Show all available options
mbench --help
mbench run --help

# Run with custom configuration
mbench run --config configs/models/default.yaml --model qwen3-235b

# Initialize configuration templates
mbench config init --template full

# Validate configuration
mbench config validate --config configs/models/default.yaml
```

## Evaluation Metrics

MobilityBench evaluates agents across 5 dimensions:

### 1. Tool Call Metric

Evaluates the quality of tool/API calls made by the agent:

- **Coverage**: Percentage of required tools that were called
- **Redundancy**: Ratio of redundant/unnecessary tool calls
- **Schema Compliance**: Whether tool parameters match the expected schema
- **Parameter Accuracy**: Accuracy of parameter values

### 2. Instruction Metric

Measures how well the agent understands user intent:

- Uses semantic similarity (SentenceTransformer) to compare extracted intent with ground truth
- Configurable similarity threshold (default: 0.7)

### 3. Planning Metric

Evaluates the agent's planning quality using:

- **DEC (Decision Coverage)**: Weighted combination of recall and precision for planning steps
- **DEP (Decision Efficiency)**: Ratio of optimal steps to actual steps taken
- Configurable alpha/beta weights for DEC calculation

### 4. Answer Metric

Assesses the accuracy of final answers:

- Task-type specific evaluation (route, POI, weather, etc.)
- Distance/coordinate tolerance for location-based answers
- Semantic matching for textual answers

### 5. Efficiency Metric

Measures resource utilization:

- **Token Usage**: Input/output tokens consumed
- **Execution Time**: Total time to complete the task
- **Tool Call Count**: Number of API calls made

## Configuration

### Directory Structure

```
configs/
├── models/
│   └── default.yaml      # Model configurations
├── datasets/
│   └── mobility_6262.yaml # Dataset specifications
└── evaluation/
    └── default.yaml      # Evaluation parameters
```

### Model Configuration

```yaml
# configs/models/default.yaml
models:
  gpt4.1:
    provider: openai
    base_url: ${LLM_BASE_URL}
    api_key: ${LLM_API_KEY}
    temperature: 0.1
    max_tokens: 8192
    roles:
      planner: gpt-4.1
      worker: gpt-4.1
      reporter: gpt-4.1
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `LLM_BASE_URL` | Base URL for LLM API |
| `LLM_API_KEY` | API key for authentication |
| `MB_CONFIG_PATH` | Custom configuration directory |
| `MB_DATA_PATH` | Custom data directory |

## Project Structure

```
mobility-bench/
├── src/mobility_bench/
│   ├── cli/              # Command-line interface
│   │   ├── main.py       # CLI entry point
│   │   ├── run.py        # Benchmark execution
│   │   ├── evaluate.py   # Evaluation runner
│   │   ├── report.py     # Report generation
│   │   └── config.py     # Configuration management
│   ├── agent/            # Agent implementation
│   │   ├── graph/        # LangGraph state and builder
│   │   │   ├── state.py  # State definitions
│   │   │   ├── builder.py # Graph builder router
│   │   │   └── decorators.py # Execution decorators
│   │   ├── roles/        # Agent role definitions
│   │   │   ├── llm_manager.py # LLM configuration
│   │   │   └── agent_factory.py # Agent creation
│   │   ├── frameworks/   # Agent frameworks
│   │   │   ├── base.py   # BaseFramework ABC
│   │   │   ├── plan_and_execute/ # Plan-and-Execute framework
│   │   │   │   ├── builder.py
│   │   │   │   └── nodes.py
│   │   │   └── react/    # ReAct framework
│   │   │       ├── builder.py
│   │   │       └── nodes.py
│   │   ├── prompts/      # Prompt templates
│   │   │   ├── plan_and_execute/
│   │   │   └── react/
│   │   └── utils/        # Agent utilities
│   │       ├── telemetry.py # Tracing and logging
│   │       └── state_context.py # State management
│   ├── tools/            # Tool registry and implementations
│   │   ├── registry.py   # Tool registration
│   │   └── sandbox/      # Sandbox tool implementations
│   ├── evaluation/       # Evaluation metrics
│   │   └── metrics/      # Individual metric implementations
│   ├── dataset/          # Dataset loading and schema
│   ├── runner/           # Batch execution runner
│   ├── reporting/        # Report generators
│   ├── config/           # Configuration management
│   └── utils/            # Utility functions
├── configs/              # YAML configuration files
├── data/                 # Datasets and results
│   ├── sandbox/          # Cached API responses
│   └── results/          # Evaluation results
└── tests/                # Unit tests
```

## Supported Models

| Model | Provider | Notes |
|-------|----------|-------|
| GPT-4.1 | OpenAI | Latest GPT-4 variant |
| Claude Opus 4.5 | Anthropic | Most capable Claude |
| Claude Sonnet 4.5 | Anthropic | Balanced performance |
| Gemini 3 Flash | Google | Fast inference |
| Gemini 3 Pro | Google | High capability |
| DeepSeek V3.2 | DeepSeek | Open-weight model |
| Qwen3-4B/30B/32B/235B | Alibaba | Various sizes |

## Development

### Setup Development Environment

```bash
# Install all dependencies including dev tools
uv sync --extra all

# Run linter
uv run ruff check src/

# Run tests
uv run pytest

# Format code
uv run ruff format src/
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/mobility_bench --cov-report=html

# Run specific test file
pytest tests/test_evaluation.py
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting (`uv run ruff check src/ && uv run pytest`)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use MobilityBench in your research, please cite:

```bibtex
@software{mobilitybench2026,
  title = {MobilityBench: A Comprehensive Evaluation Framework for Mobility AI Agents},
  year = {2026},
  url = {https://github.com/your-org/mobility-bench}
}
```

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) for agent orchestration
- [Typer](https://typer.tiangolo.com/) for CLI framework
- [Rich](https://rich.readthedocs.io/) for terminal formatting
