#!/usr/bin/env python3
"""
Aggregate a single trace into a markdown/console summary (durations, tool counts, failures).
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.trace_reader import load_trace_data


def format_table(rows):
    widths = [
        max(len(str(col)) for col in column) for column in zip(*rows, strict=False)
    ]
    lines = []
    for row in rows:
        line = " | ".join(
            str(col).ljust(width) for col, width in zip(row, widths, strict=False)
        )
        lines.append(line)
    lines.insert(1, "-+-".join("-" * w for w in widths))
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze a trace and output summary stats."
    )
    parser.add_argument("trace_id", help="Trace ID to analyze")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Optional markdown file to write (defaults to stdout)",
    )
    args = parser.parse_args()

    trace = load_trace_data(args.trace_id)
    spans = trace.get("spans", [])
    events = trace.get("events", [])

    if not spans:
        raise SystemExit(f"No spans found for trace {args.trace_id}")

    durations = []
    per_node = defaultdict(float)
    llm_calls = 0
    tool_calls = 0

    for span in spans:
        duration = float(span.get("duration_ms", 0.0))
        durations.append(duration)
        name = span.get("name", "unknown")
        per_node[name] += duration
        if name.startswith("llm"):
            llm_calls += 1
        if name.startswith("tool"):
            tool_calls += 1

    total_ms = sum(durations)
    per_node_rows = [
        ("Span name", "Duration (ms)", "Share (%)"),
        *[
            (
                name,
                f"{duration:.2f}",
                f"{(duration / total_ms * 100):.1f}",
            )
            for name, duration in sorted(
                per_node.items(), key=lambda item: item[1], reverse=True
            )
        ],
    ]

    event_types = Counter(event["event_type"] for event in events)

    summary_lines = [
        f"# Trace Summary - {args.trace_id}",
        "",
        f"- Total duration: {total_ms:.2f} ms",
        f"- Span count: {len(spans)}",
        f"- LLM calls: {llm_calls}",
        f"- Tool calls: {tool_calls}",
        "",
        "## Events",
        *(f"- {etype}: {count}" for etype, count in event_types.items()),
        "",
        "## Span Breakdown",
        "```\n" + format_table(per_node_rows) + "\n```",
    ]

    output_text = "\n".join(summary_lines)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output_text, encoding="utf-8")
        print(f"Summary written to {args.output}")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
