#!/usr/bin/env python3
"""
Render a textual Gantt-like overview for a trace, useful for quick CLI inspections.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.trace_reader import load_trace_data


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def main() -> None:
    parser = argparse.ArgumentParser(description="Show textual timeline for a trace.")
    parser.add_argument("trace_id", help="Trace ID to render")
    parser.add_argument(
        "--scale",
        type=float,
        default=10.0,
        help="Milliseconds per character (default: 10ms)",
    )
    args = parser.parse_args()

    trace = load_trace_data(args.trace_id)
    spans = trace.get("spans", [])
    if not spans:
        raise SystemExit(f"No spans found for trace {args.trace_id}")

    ordered = sorted(spans, key=lambda span: span.get("start_time", ""))
    base_time = _parse_iso(ordered[0]["start_time"])

    print(f"# Trace timeline: {args.trace_id}")
    print(f"# Scale: {args.scale} ms per character\n")

    for span in ordered:
        start_dt = _parse_iso(span["start_time"])
        end_dt = _parse_iso(span["end_time"])
        duration_ms = (end_dt - start_dt).total_seconds() * 1000
        offset_chars = int(((start_dt - base_time).total_seconds() * 1000) / args.scale)
        bar_chars = max(1, int(duration_ms / args.scale))
        bar = " " * offset_chars + "#" * bar_chars
        print(f"{span['name']:<24} | {duration_ms:>8.2f} ms | {bar}")


if __name__ == "__main__":
    main()
