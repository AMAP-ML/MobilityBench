"""
Telemetry utilities for local-only tracing, structured event logging, and span export.

This module wires up OpenTelemetry SDK with two exporters:
1. Console exporter for quick visual verification.
2. JSON file exporter writes spans to logs/span_dump.jsonl for offline tooling.

It also provides helper context managers/utilities to attach trace/span ids to
application logs and emit structured events.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import Span, SpanKind

# -----------------------------------------------------------------------------
# Paths & files
# -----------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parents[4]  # mobility_bench root
LOG_DIR = ROOT_DIR / "logs"
SPAN_DUMP_FILE = LOG_DIR / "span_dump.jsonl"
EVENT_LOG_FILE = LOG_DIR / "events.jsonl"

LOG_DIR.mkdir(parents=True, exist_ok=True)

_FILE_LOCK = threading.Lock()


def _write_json_line(path: Path, data: dict[str, Any]) -> None:
    """Append a JSON object to the target file safely."""
    serialized = json.dumps(data, ensure_ascii=False)
    with _FILE_LOCK:
        with path.open("a", encoding="utf-8") as fp:
            fp.write(serialized + "\n")


# -----------------------------------------------------------------------------
# Span exporter that flushes readable spans to JSONL
# -----------------------------------------------------------------------------


def _format_trace_id(trace_id: int) -> str:
    return f"{trace_id:032x}"


def _format_span_id(span_id: int) -> str:
    return f"{span_id:016x}"


def _ns_timestamp_to_iso(ns_timestamp: int) -> str:
    dt = datetime.fromtimestamp(ns_timestamp / 1_000_000_000, tz=UTC)
    return dt.isoformat()


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, list | tuple | set):
        return [_sanitize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _sanitize_value(v) for k, v in value.items()}
    if hasattr(value, "model_dump"):
        return _sanitize_value(value.model_dump())
    return str(value)


class CompactConsoleSpanExporter(SpanExporter):
    """Compact console span exporter, outputs key information only."""

    def __init__(self):
        # Silent mode - no console output
        # Detailed info is written to span_dump.jsonl file
        pass

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export span - silent mode, no console output."""
        # Completely disable console output to avoid verbose JSON output
        # For detailed info, use logs/span_dump.jsonl file or related tools
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return


class JsonFileSpanExporter(SpanExporter):
    """Simple span exporter that writes each span as a JSON line."""

    def __init__(self, file_path: Path):
        self._file_path = file_path

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        try:
            payload = []
            for span in spans:
                ctx = span.get_span_context()
                parent_span_id = (
                    _format_span_id(span.parent.span_id)
                    if span.parent is not None
                    else None
                )
                payload.append(
                    {
                        "trace_id": _format_trace_id(ctx.trace_id),
                        "span_id": _format_span_id(ctx.span_id),
                        "parent_span_id": parent_span_id,
                        "name": span.name,
                        "kind": span.kind.name
                        if isinstance(span.kind, SpanKind)
                        else str(span.kind),
                        "status": span.status.status_code.name,
                        "start_time": _ns_timestamp_to_iso(span.start_time),
                        "end_time": _ns_timestamp_to_iso(span.end_time),
                        "duration_ms": (span.end_time - span.start_time) / 1_000_000,
                        "attributes": {
                            str(key): _sanitize_value(value)
                            for key, value in span.attributes.items()
                        },
                        "events": [
                            {
                                "name": event.name,
                                "timestamp": _ns_timestamp_to_iso(event.timestamp),
                                "attributes": {
                                    str(k): _sanitize_value(v)
                                    for k, v in event.attributes.items()
                                },
                            }
                            for event in span.events
                        ],
                    }
                )

            if payload:
                for record in payload:
                    _write_json_line(self._file_path, record)
            return SpanExportResult.SUCCESS
        except Exception:  # pragma: no cover - defensive logging
            return SpanExportResult.FAILURE

    def shutdown(self) -> None:  # pragma: no cover - nothing to cleanup
        return


# -----------------------------------------------------------------------------
# Tracer provider bootstrap
# -----------------------------------------------------------------------------

_PROVIDER_INITIALIZED = False


def _configure_tracer_provider() -> None:
    global _PROVIDER_INITIALIZED
    if _PROVIDER_INITIALIZED:
        return

    resource = Resource.create({"service.name": "mobility-bench-agent"})
    provider = TracerProvider(resource=resource)
    # Use compact console exporter to reduce output
    provider.add_span_processor(BatchSpanProcessor(CompactConsoleSpanExporter()))
    # Write complete info to file
    provider.add_span_processor(
        BatchSpanProcessor(JsonFileSpanExporter(SPAN_DUMP_FILE))
    )
    trace.set_tracer_provider(provider)
    _PROVIDER_INITIALIZED = True


def get_tracer(component: str | None = None):
    """Return an OpenTelemetry tracer for the given component."""
    _configure_tracer_provider()
    name = component or __name__
    return trace.get_tracer(name)


# -----------------------------------------------------------------------------
# Context helpers for trace/span propagation outside of OTel ecosystem
# -----------------------------------------------------------------------------

_trace_id_ctx: ContextVar[str] = ContextVar("pf_trace_id", default="")
_span_id_ctx: ContextVar[str] = ContextVar("pf_span_id", default="")


def get_current_trace_id() -> str:
    return _trace_id_ctx.get()


def get_current_span_id() -> str:
    return _span_id_ctx.get()


def _set_span_context(span: Span) -> tuple[Any, Any]:
    ctx = span.get_span_context()
    trace_id = _format_trace_id(ctx.trace_id)
    span_id = _format_span_id(ctx.span_id)
    token_trace = _trace_id_ctx.set(trace_id)
    token_span = _span_id_ctx.set(span_id)
    return token_trace, token_span


def _reset_span_context(tokens: tuple[Any, Any]) -> None:
    token_trace, token_span = tokens
    _trace_id_ctx.reset(token_trace)
    _span_id_ctx.reset(token_span)


@contextmanager
def start_span(name: str, **kwargs):
    """Context manager for starting a span and exposing ids through ContextVar."""
    tracer = get_tracer(kwargs.pop("component", __name__))
    with tracer.start_as_current_span(name, **kwargs) as span:
        tokens = _set_span_context(span)
        try:
            yield span
        finally:
            try:
                _reset_span_context(tokens)
            except ValueError:
                # Catch cross-thread/context reset exception to avoid affecting main flow
                pass


def trace_context(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a dictionary containing current trace/span ids plus optional data."""
    ctx = {
        "trace_id": get_current_trace_id(),
        "span_id": get_current_span_id(),
    }
    if extra:
        ctx.update(extra)
    return ctx


# -----------------------------------------------------------------------------
# Structured event logging helpers
# -----------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


def log_event(
    event_type: str,
    payload: dict[str, Any] | None = None,
    *,
    timestamp: datetime | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> None:
    """Emit a structured event to events.jsonl with trace correlation ids."""
    ts = timestamp or _now()
    record = {
        "event_type": event_type,
        "absolute_ts": ts.isoformat(),
        "epoch_ms": int(ts.timestamp() * 1000),
        "trace_id": trace_id or get_current_trace_id(),
        "span_id": span_id or get_current_span_id(),
        "payload": _sanitize_value(payload or {}),
    }
    _write_json_line(EVENT_LOG_FILE, record)


def iso_utc_now() -> str:
    return _now().isoformat()


def epoch_ms_now() -> int:
    return int(_now().timestamp() * 1000)


__all__ = [
    "start_span",
    "trace_context",
    "log_event",
    "get_tracer",
    "get_current_trace_id",
    "get_current_span_id",
    "iso_utc_now",
    "epoch_ms_now",
    "SpanKind",
]
