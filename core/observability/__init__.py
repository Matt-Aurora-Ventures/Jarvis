"""OpenTelemetry observability setup."""
from core.observability.otel_setup import (
    setup_telemetry,
    get_tracer,
    get_meter,
    trace_function,
    record_metric,
)

__all__ = [
    "setup_telemetry",
    "get_tracer",
    "get_meter",
    "trace_function",
    "record_metric",
]
