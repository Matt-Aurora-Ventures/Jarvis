"""Distributed tracing utilities."""
import uuid
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from contextlib import contextmanager
from contextvars import ContextVar
import logging
import json

logger = logging.getLogger(__name__)

# Context variables for trace propagation
_current_trace: ContextVar[Optional["Span"]] = ContextVar("current_trace", default=None)
_current_span: ContextVar[Optional["Span"]] = ContextVar("current_span", default=None)


@dataclass
class Span:
    """A span in a distributed trace."""
    trace_id: str
    span_id: str
    name: str
    parent_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: str = "OK"
    tags: Dict[str, str] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    
    def set_tag(self, key: str, value: str):
        """Add a tag to the span."""
        self.tags[key] = str(value)
    
    def log(self, message: str, **fields):
        """Add a log entry to the span."""
        self.logs.append({
            "timestamp": time.time(),
            "message": message,
            **fields
        })
    
    def set_error(self, error: Exception):
        """Mark span as error."""
        self.status = "ERROR"
        self.set_tag("error", "true")
        self.set_tag("error.type", type(error).__name__)
        self.set_tag("error.message", str(error))
    
    def finish(self):
        """Finish the span."""
        self.end_time = time.time()
    
    @property
    def duration_ms(self) -> float:
        """Get span duration in milliseconds."""
        end = self.end_time or time.time()
        return (end - self.start_time) * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentId": self.parent_id,
            "name": self.name,
            "startTime": int(self.start_time * 1000000),  # microseconds
            "duration": int(self.duration_ms * 1000),  # microseconds
            "status": self.status,
            "tags": self.tags,
            "logs": self.logs
        }


class Tracer:
    """Distributed tracing manager."""
    
    def __init__(self, service_name: str = "jarvis"):
        self.service_name = service_name
        self._spans: List[Span] = []
        self._exporters: List[callable] = []
    
    def start_span(
        self,
        name: str,
        trace_id: str = None,
        parent_id: str = None,
        tags: Dict[str, str] = None
    ) -> Span:
        """Start a new span."""
        current = _current_span.get()
        
        if trace_id is None:
            if current:
                trace_id = current.trace_id
            else:
                trace_id = uuid.uuid4().hex
        
        if parent_id is None and current:
            parent_id = current.span_id
        
        span = Span(
            trace_id=trace_id,
            span_id=uuid.uuid4().hex[:16],
            name=name,
            parent_id=parent_id,
            tags=tags or {}
        )
        
        span.set_tag("service", self.service_name)
        
        _current_span.set(span)
        return span
    
    def finish_span(self, span: Span):
        """Finish a span and export it."""
        span.finish()
        self._spans.append(span)
        
        # Export
        for exporter in self._exporters:
            try:
                exporter(span)
            except Exception as e:
                logger.error(f"Failed to export span: {e}")
        
        # Keep only last 1000 spans
        if len(self._spans) > 1000:
            self._spans = self._spans[-1000:]
    
    @contextmanager
    def span(self, name: str, **tags):
        """Context manager for creating spans."""
        span = self.start_span(name, tags=tags)
        try:
            yield span
        except Exception as e:
            span.set_error(e)
            raise
        finally:
            self.finish_span(span)
    
    def add_exporter(self, exporter: callable):
        """Add a span exporter."""
        self._exporters.append(exporter)
    
    def get_trace(self, trace_id: str) -> List[Span]:
        """Get all spans for a trace."""
        return [s for s in self._spans if s.trace_id == trace_id]
    
    def get_recent_traces(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent unique traces."""
        traces = {}
        for span in reversed(self._spans):
            if span.trace_id not in traces:
                traces[span.trace_id] = {
                    "trace_id": span.trace_id,
                    "root_span": span.name if span.parent_id is None else None,
                    "span_count": 0,
                    "duration_ms": 0,
                    "status": "OK"
                }
            traces[span.trace_id]["span_count"] += 1
            if span.parent_id is None:
                traces[span.trace_id]["root_span"] = span.name
                traces[span.trace_id]["duration_ms"] = span.duration_ms
            if span.status == "ERROR":
                traces[span.trace_id]["status"] = "ERROR"
            
            if len(traces) >= limit:
                break
        
        return list(traces.values())


# JSON exporter for file logging
def json_file_exporter(path: str = "logs/traces.jsonl"):
    """Create a JSON file exporter."""
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    def export(span: Span):
        with open(path, "a") as f:
            f.write(json.dumps(span.to_dict()) + "\n")
    
    return export


# Console exporter for debugging
def console_exporter(span: Span):
    """Export spans to console."""
    logger.debug(f"Span: {span.name} ({span.duration_ms:.2f}ms) - {span.status}")


# Global tracer
tracer = Tracer()


def get_current_trace_id() -> Optional[str]:
    """Get current trace ID from context."""
    span = _current_span.get()
    return span.trace_id if span else None


def get_current_span_id() -> Optional[str]:
    """Get current span ID from context."""
    span = _current_span.get()
    return span.span_id if span else None
