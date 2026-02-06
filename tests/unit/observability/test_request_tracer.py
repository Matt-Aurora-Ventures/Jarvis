"""
Unit tests for RequestTracer in core/observability/tracing.py

Tests the RequestTracer class for:
- Starting traces
- Ending traces
- Adding spans
- Trace lifecycle management
"""

import pytest
import time
from unittest.mock import patch


class TestRequestTracer:
    """Test RequestTracer class functionality."""

    def test_request_tracer_initialization(self):
        """RequestTracer should initialize properly."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        assert tracer is not None

    def test_start_trace_returns_trace_id(self):
        """start_trace should return a unique trace ID."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("test_operation")

        assert trace_id is not None
        assert isinstance(trace_id, str)
        assert len(trace_id) > 0

    def test_start_trace_unique_ids(self):
        """start_trace should return unique IDs for each call."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id_1 = tracer.start_trace("operation_1")
        trace_id_2 = tracer.start_trace("operation_2")

        assert trace_id_1 != trace_id_2

    def test_start_trace_stores_operation_name(self):
        """start_trace should store the operation name."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("my_operation")

        trace_info = tracer.get_trace(trace_id)
        assert trace_info is not None
        assert trace_info["operation"] == "my_operation"

    def test_end_trace_marks_completion(self):
        """end_trace should mark the trace as complete."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("test_op")
        tracer.end_trace(trace_id)

        trace_info = tracer.get_trace(trace_id)
        assert trace_info["status"] == "completed"
        assert trace_info["end_time"] is not None

    def test_end_trace_calculates_duration(self):
        """end_trace should calculate trace duration."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("test_op")
        time.sleep(0.01)  # 10ms
        tracer.end_trace(trace_id)

        trace_info = tracer.get_trace(trace_id)
        assert trace_info["duration_ms"] >= 10

    def test_end_trace_with_error(self):
        """end_trace should accept error status."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("test_op")
        tracer.end_trace(trace_id, status="error", error="Connection failed")

        trace_info = tracer.get_trace(trace_id)
        assert trace_info["status"] == "error"
        assert trace_info["error"] == "Connection failed"

    def test_add_span_to_trace(self):
        """add_span should add a span to an existing trace."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("parent_op")

        span_id = tracer.add_span(trace_id, "child_span", {"key": "value"})

        assert span_id is not None
        trace_info = tracer.get_trace(trace_id)
        assert len(trace_info["spans"]) >= 1

    def test_add_span_stores_data(self):
        """add_span should store the span data."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("parent")

        tracer.add_span(trace_id, "db_query", {
            "query": "SELECT * FROM users",
            "rows_returned": 42
        })

        trace_info = tracer.get_trace(trace_id)
        span = trace_info["spans"][0]
        assert span["name"] == "db_query"
        assert span["data"]["query"] == "SELECT * FROM users"
        assert span["data"]["rows_returned"] == 42

    def test_add_span_timestamps(self):
        """add_span should record timestamp."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("parent")
        tracer.add_span(trace_id, "span1", {})

        trace_info = tracer.get_trace(trace_id)
        span = trace_info["spans"][0]
        assert "timestamp" in span
        assert span["timestamp"] is not None

    def test_add_multiple_spans(self):
        """Should be able to add multiple spans to a trace."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("parent")

        tracer.add_span(trace_id, "span1", {"step": 1})
        tracer.add_span(trace_id, "span2", {"step": 2})
        tracer.add_span(trace_id, "span3", {"step": 3})

        trace_info = tracer.get_trace(trace_id)
        assert len(trace_info["spans"]) == 3

    def test_add_span_invalid_trace_id(self):
        """add_span should handle invalid trace ID gracefully."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        result = tracer.add_span("nonexistent_trace", "span", {})

        assert result is None

    def test_end_trace_invalid_trace_id(self):
        """end_trace should handle invalid trace ID gracefully."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        # Should not raise exception
        tracer.end_trace("nonexistent_trace")

    def test_get_trace_not_found(self):
        """get_trace should return None for unknown trace ID."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        result = tracer.get_trace("unknown")

        assert result is None

    def test_get_active_traces(self):
        """Should be able to get list of active traces."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id_1 = tracer.start_trace("op1")
        trace_id_2 = tracer.start_trace("op2")
        tracer.end_trace(trace_id_1)

        active = tracer.get_active_traces()
        assert trace_id_2 in active
        assert trace_id_1 not in active


class TestRequestTracerCleanup:
    """Test trace cleanup functionality."""

    def test_cleanup_old_traces(self):
        """Should be able to cleanup old completed traces."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("old_op")
        tracer.end_trace(trace_id)

        # Cleanup traces older than 0 seconds (all completed traces)
        tracer.cleanup(max_age_seconds=0)

        assert tracer.get_trace(trace_id) is None

    def test_cleanup_preserves_recent_traces(self):
        """Cleanup should preserve recent traces."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("recent_op")
        tracer.end_trace(trace_id)

        # Cleanup traces older than 1 hour
        tracer.cleanup(max_age_seconds=3600)

        assert tracer.get_trace(trace_id) is not None

    def test_cleanup_preserves_active_traces(self):
        """Cleanup should never remove active traces."""
        from core.observability.tracing import RequestTracer

        tracer = RequestTracer()
        trace_id = tracer.start_trace("active_op")

        # Cleanup all
        tracer.cleanup(max_age_seconds=0)

        assert tracer.get_trace(trace_id) is not None


class TestRequestTracerIntegration:
    """Test RequestTracer integration with existing TraceContext."""

    def test_works_with_trace_context(self):
        """RequestTracer should work alongside existing TraceContext."""
        from core.observability.tracing import RequestTracer, TraceContext

        tracer = RequestTracer()
        trace_id = tracer.start_trace("api_request")

        # Should be able to create TraceContext with same trace_id
        with TraceContext("inner_operation", trace_id=trace_id):
            tracer.add_span(trace_id, "processing", {"status": "ok"})

        tracer.end_trace(trace_id)

        trace_info = tracer.get_trace(trace_id)
        assert trace_info["status"] == "completed"
        assert len(trace_info["spans"]) == 1
