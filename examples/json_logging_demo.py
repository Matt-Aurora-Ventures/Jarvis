"""Quick demo of JSON logging output."""
from core.logging_config import setup_logging, get_logger, CorrelationContext

setup_logging(
    log_dir="logs/examples",
    log_file="json_demo.log",
    level="INFO",
    json_format=True,  # JSON format
    console_output=False,
    extra_fields={"service": "jarvis", "environment": "production"}
)

logger = get_logger(__name__)

with CorrelationContext(user_id="user_123", trade_id="trade_456"):
    logger.info("Trade executed",
        symbol="SOL",
        amount=100.5,
        price=95.23,
        tx_id="0xabcdef123456"
    )

print("Check logs/examples/json_demo.log for JSON output")
