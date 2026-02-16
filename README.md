# MobilityBench

A Benchmark for Evaluating Route-Planning Agents in Real-World Mobility Scenarios.

## Overview

**MobilityBench** is a scalable benchmark for evaluating LLM-based route-planning agents in real-world mobility scenarios. It is built from large-scale, anonymized user queries collected from **Amap**, covering a wide range of route-planning intents across **multiple cities worldwide**.

To support **reproducible end-to-end evaluation**, MobilityBench includes a **deterministic API-replay sandbox** that removes environmental variance from live services. We also introduce a **multi-dimensional evaluation protocol** centered on **outcome validity**, complemented by evaluations of **instruction understanding**, **planning**, **tool use**, and **efficiency**. 

### Key Features

- **Multi-model evaluation**: Test multiple LLMs (OpenAI, Anthropic, Google, Qwen, DeepSeek) in parallel  
- **Comprehensive metrics**: Five evaluation dimensions covering instruction understanding, planning quality, tool use, answer accuracy, and efficiency  
- **Sandbox mode**: Offline evaluation with pre-cached API responses for fully reproducible results

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
                    │  Tool Call   │
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
mbench run --model gpt4.1 --dataset data/datasets/sample_10.csv

# Run with ReAct framework
mbench run --model gpt4.1 --framework react

# Run multiple models in parallel
mbench run --models gpt4.1,claude-opus-4-5 --parallel 4

# Enable sandbox mode (offline evaluation)
mbench run --model gpt4.1 --sandbox

# Resume an interrupted run
mbench run --model gpt4.1 --resume run_20260215_120000
```


### 3. Evaluate Results

```bash
# Evaluate a single run
mbench eval --run-id run_20260215_120000

# Evaluate with specific metrics
mbench eval --run-id run_20260215_120000 --metrics tool,answer,planning

# Evaluate with a specific ground truth file
mbench eval --run-id run_20260215_120000 --ground-truth data/datasets/sample_10.csv
```

### 4. Generate Reports

```bash
# Generate markdown report
mbench report --run-id run_20260215_120000

# Generate HTML report
mbench report --run-id run_20260215_120000 --format html

# Generate Excel report (with Overall and By Intent Family sheets)
mbench report --run-id run_20260215_120000 --format excel

# Compare multiple runs
mbench report --run-id run_001 --compare run_002
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

MobilityBench evaluates agents across 5 dimensions. Each metric reports individual **sub-dimension** scores, and results are aggregated both **overall** and **by intent_family** category.

## Evaluation Metrics (MobilityBench)

MobilityBench proposes a **multi-dimensional evaluation protocol** that goes beyond end-to-end success rate, measuring an agent’s capabilities across **Instruction Understanding, Planning, Tool Use, Decision Making, and Efficiency**.

### 1) Instruction Understanding

- **Intent Detection (ID)**  
  Measures whether the agent correctly identifies the query intent (one of the benchmark’s scenario labels).  
  *Scoring:* label similarity ≥ threshold.

- **Information Extraction (IE)**  
  Measures whether the agent correctly extracts all constraints/slots from the query (e.g., origin/destination, time constraints, preferences).  
  *Scoring:* exact match between predicted and ground-truth constraint sets.

---

### 2) Planning

- **Task Decomposition (DEC)**  
  Measures whether the agent decomposes the task into an appropriate sequence of atomic actions. Reported as two metrics:
  - **DEC-P (Decomposition Precision / Coverage)**: proportion of ground-truth steps covered by predicted steps  
  - **DEC-R (Decomposition Recall / Redundancy complement)**: proportion of predicted steps that match ground-truth steps  
  *(Matching is determined by an action-level equivalence function.)*

---

### 3) Tool Use

- **Tool Selection (TS)**  
  Measures whether the agent selects the correct set of tools needed for the task. Reported as:
  - **TS-P (Tool Coverage)**: fraction of required tools selected
  - **TS-R (Non-redundancy / 1 - redundancy)**: penalizes unnecessary tool calls

- **Schema Compliance (SC)**  
  Measures whether tool/API calls conform to tool specifications (mandatory parameters present, types/formats/ranges valid).  
  *Scoring:* averaged compliance across all tool calls in an episode.

---

### 4) Decision Making (Outcome Quality)

- **Delivery Rate (DR)**  
  Percentage of queries where the agent produces a **complete, executable final output**, without interruption or tool invocation failure.

- **Final Pass Rate (FPR)**  
  Percentage of queries where the final solution **satisfies all explicit and implicit user constraints** (i.e., a valid final outcome).

---

### 5) Efficiency

- **Input Tokens (IT)**  
  Total tokens consumed as input context (system prompt + instructions + accumulated action/observation history).

- **Output Tokens (OT)**  
  Total tokens generated by the model (reflecting generation cost/latency trade-offs).

## Configuration

### Dataset Format

MobilityBench supports CSV datasets. The recommended format is CSV with the following key fields:

| Field | Description |
|-------|-------------|
| `query` | User query text |
| `context` | Context information (JSON string, e.g. current location, city) |


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
      planner: gpt-41-0414-global
      worker: gpt-41-0414-global
      reporter: gpt-41-0414-global
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `LLM_BASE_URL` | Base URL for LLM API |
| `LLM_API_KEY` | API key for authentication |

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
│   │   ├── schema.py     # Case, GroundTruth, RunResult dataclasses
│   │   └── loader.py     # CSV/Excel/JSON loader with JSON field parsing
│   ├── runner/           # Batch execution runner
│   │   ├── base.py       # BaseRunner with progress callback support
│   │   └── batch.py      # BatchRunner with parallel execution
│   ├── reporting/        # Report generators (Markdown/HTML/Excel)
│   ├── config/           # Configuration management
│   └── utils/            # Utility functions
├── configs/              # YAML configuration files
├── data/                 # Datasets and results
│   ├── datasets/         # CSV/Excel/JSON datasets
│   ├── sandbox/          # Cached API responses
│   └── results/          # Run outputs and evaluation results
└── tests/                # Unit tests
```

## Supported Models

| Model | Provider | Notes |
|-------|----------|-------|
| GPT-4.1 GPT-5.2 | OpenAI | Latest GPT variant |
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