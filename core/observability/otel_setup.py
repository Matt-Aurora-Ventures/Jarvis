"""OpenTelemetry setup for distributed tracing and metrics."""
import os
import functools
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace, metrics
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.semconv.resource import ResourceAttributes
    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False
    trace = None
    metrics = None

_tracer: Optional[object] = None
_meter: Optional[object] = None
_initialized = False


def setup_telemetry(
    service_name: str = "jarvis",
    service_version: str = "4.1.1",
    environment: str = None,
    enable_console_export: bool = False,
    otlp_endpoint: str = None,
) -> bool:
    """
    Initialize OpenTelemetry tracing and metrics.
    
    Args:
        service_name: Name of the service
        service_version: Version string
        environment: Deployment environment
        enable_console_export: Enable console output for debugging
        otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
        
    Returns:
        True if setup succeeded
    """
    global _tracer, _meter, _initialized
    
    if not HAS_OTEL:
        logger.warning("OpenTelemetry not installed. Observability disabled.")
        return False
    
    if _initialized:
        return True
    
    env = environment or os.getenv("ENVIRONMENT", "development")
    
    # Create resource with service info
    resource = Resource.create({
        ResourceAttributes.SERVICE_NAME: service_name,
        ResourceAttributes.SERVICE_VERSION: service_version,
        ResourceAttributes.DEPLOYMENT_ENVIRONMENT: env,
    })
    
    # Setup tracing
    tracer_provider = TracerProvider(resource=resource)
    
    if enable_console_export:
        tracer_provider.add_span_processor(
            BatchSpanProcessor(ConsoleSpanExporter())
        )
    
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP tracing enabled: {otlp_endpoint}")
        except ImportError:
            logger.warning("OTLP exporter not installed")
    
    trace.set_tracer_provider(tracer_provider)
    _tracer = trace.get_tracer(service_name, service_version)
    
    # Setup metrics
    metric_readers = []
    
    if enable_console_export:
        metric_readers.append(
            PeriodicExportingMetricReader(ConsoleMetricExporter())
        )
    
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            otlp_metric_exporter = OTLPMetricExporter(endpoint=otlp_endpoint)
            metric_readers.append(
                PeriodicExportingMetricReader(otlp_metric_exporter)
            )
        except ImportError:
            pass
    
    meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
    metrics.set_meter_provider(meter_provider)
    _meter = metrics.get_meter(service_name, service_version)
    
    _initialized = True
    logger.info(f"OpenTelemetry initialized for {service_name} v{service_version}")
    return True


def get_tracer(name: str = None):
    """Get the OpenTelemetry tracer."""
    if not HAS_OTEL or _tracer is None:
        return None
    return _tracer


def get_meter(name: str = None):
    """Get the OpenTelemetry meter."""
    if not HAS_OTEL or _meter is None:
        return None
    return _meter


def trace_function(name: str = None, attributes: dict = None):
    """
    Decorator to trace a function with OpenTelemetry.
    
    Usage:
        @trace_function("my_operation")
        def my_func():
            pass
    """
    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not HAS_OTEL or _tracer is None:
                return func(*args, **kwargs)
            
            with _tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.StatusCode.OK)
                    return result
                except Exception as e:
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    span.record_exception(e)
                    raise
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not HAS_OTEL or _tracer is None:
                return await func(*args, **kwargs)
            
            with _tracer.start_as_current_span(span_name) as span:
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
                try:
                    result = await func(*args, **kwargs)
                    span.set_status(trace.StatusCode.OK)
                    return result
                except Exception as e:
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    span.record_exception(e)
                    raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def record_metric(name: str, value: float, attributes: dict = None):
    """Record a metric value."""
    if not HAS_OTEL or _meter is None:
        return
    
    # Create counter for the metric
    counter = _meter.create_counter(
        name,
        description=f"Counter for {name}",
    )
    counter.add(value, attributes or {})


def instrument_fastapi(app):
    """Instrument a FastAPI app with OpenTelemetry."""
    if not HAS_OTEL:
        return
    
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except ImportError:
        logger.warning("FastAPI OpenTelemetry instrumentation not installed")
