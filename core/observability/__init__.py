"""OpenTelemetry observability setup and lightweight tracing."""
from core.observability.otel_setup import (
    setup_telemetry,
    get_tracer,
    get_meter,
    trace_function,
    record_metric,
)

# Lightweight tracing (works without OpenTelemetry)
from core.observability.tracing import (
    TraceContext,
    Span,
    get_current_trace,
    get_trace_id,
    get_span_id,
    traced,
    TracedLogger,
    get_traced_logger,
    create_correlation_context,
    generate_trace_id,
)

__all__ = [
    # OpenTelemetry
    "setup_telemetry",
    "get_tracer",
    "get_meter",
    "trace_function",
    "record_metric",
    # Lightweight tracing
    "TraceContext",
    "Span",
    "get_current_trace",
    "get_trace_id",
    "get_span_id",
    "traced",
    "TracedLogger",
    "get_traced_logger",
    "create_correlation_context",
    "generate_trace_id",
]
