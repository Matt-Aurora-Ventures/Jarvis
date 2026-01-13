"""Structured JSON logging."""
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict
from pathlib import Path

try:
    from api.middleware.request_tracing import get_request_id
except ImportError:
    def get_request_id():
        return ""


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        request_id = get_request_id()
        if request_id:
            log_data["request_id"] = request_id
        
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, default=str)


class ContextLogger(logging.LoggerAdapter):
    """Logger with persistent context."""
    
    def process(self, msg, kwargs):
        extra = kwargs.get('extra', {})
        extra.update(self.extra)
        kwargs['extra'] = extra
        return msg, kwargs


def setup_structured_logging(level: int = logging.INFO, log_file: str = None):
    """Configure structured logging."""
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = []
    
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(StructuredFormatter())
    root.addHandler(console)
    
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(StructuredFormatter())
        root.addHandler(file_handler)
    
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str, **context) -> ContextLogger:
    """Get a logger with context."""
    return ContextLogger(logging.getLogger(name), context)
