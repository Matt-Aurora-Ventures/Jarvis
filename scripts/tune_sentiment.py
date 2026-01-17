"""
Sentiment Weight Tuning Cron Job

Runs every 6 hours to automatically adjust sentiment component weights
based on prediction outcome correlations.

Schedule (via cron or systemd timer):
0 */6 * * * cd /path/to/Jarvis && python scripts/tune_sentiment.py

Or as systemd timer:
/etc/systemd/system/tune-sentiment.timer
/etc/systemd/system/tune-sentiment.service
"""

import logging
import json
from pathlib import Path
from datetime import datetime
import sys
import os

# Fix Windows encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.sentiment.self_tuning import SelfTuningSentimentEngine

logger = logging.getLogger(__name__)


def setup_logging():
    """Setup logging to file and console."""
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "sentiment_tuning.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(),
        ],
    )

    return log_file


def main():
    """Run sentiment weight tuning."""
    log_file = setup_logging()

    logger.info("=" * 80)
    logger.info("🧠 Sentiment Weight Tuning Job Started")
    logger.info("=" * 80)

    try:
        # Initialize engine
        db_path = Path(__file__).parent.parent / "data" / "sentiment.db"
        engine = SelfTuningSentimentEngine(str(db_path))

        logger.info(f"📊 Current weights: {json.dumps(engine.weights.weights_dict, indent=2)}")

        # Run tuning with parameters
        engine.tune_weights(
            min_samples=50,  # Need at least 50 outcomes
            learning_rate=0.05,  # 5% adjustment per tuning
        )

        # Generate and log report
        report = engine.get_tuning_report()

        logger.info("\n📈 TUNING REPORT")
        logger.info(f"Total Predictions: {report.get('total_predictions', 0)}")
        logger.info(f"Win Rate: {report.get('win_rate', 0):.1f}%")
        logger.info(f"Current Weights: {json.dumps(report.get('current_weights', {}), indent=2)}")

        if report.get("component_performance"):
            logger.info("\n🎯 Component Performance:")
            for component, perf in report["component_performance"].items():
                logger.info(f"  {component}: {perf:.3f}")

        # Log updated weights
        logger.info(f"\n✅ Updated weights: {json.dumps(engine.weights.weights_dict, indent=2)}")

        logger.info("\n" + "=" * 80)
        logger.info("✅ Tuning job completed successfully")
        logger.info("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"❌ Error during tuning: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
