#!/usr/bin/env python3
"""
JARVIS Monitoring Dashboard Startup Script

Starts the monitoring dashboard web server.

Usage:
    python scripts/start_dashboard.py
    python scripts/start_dashboard.py --port 9090
    python scripts/start_dashboard.py --config lifeos/config/monitoring.json
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))


def load_env():
    """Load environment variables from .env files."""
    env_files = [
        project_root / "tg_bot" / ".env",
        project_root / "bots" / "twitter" / ".env",
        project_root / ".env",
    ]
    for env_path in env_files:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        os.environ.setdefault(key.strip(), value.strip())


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="JARVIS Monitoring Dashboard")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MONITORING_PORT", "8080")),
        help="Port to run dashboard on (default: 8080)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MONITORING_HOST", "0.0.0.0"),
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--data-dir",
        default=str(project_root / "data"),
        help="Data directory for metrics storage",
    )
    parser.add_argument(
        "--config-dir",
        default=str(project_root / "lifeos" / "config"),
        help="Configuration directory",
    )
    parser.add_argument(
        "--config",
        help="Path to monitoring config JSON file",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(project_root / "logs" / "dashboard.log", encoding="utf-8"),
        ]
    )

    # Ensure logs directory exists
    (project_root / "logs").mkdir(exist_ok=True)

    # Load environment
    load_env()

    # Load config if provided
    port = args.port
    if args.config and Path(args.config).exists():
        try:
            import json
            with open(args.config) as f:
                config = json.load(f)
            port = config.get("port", port)
        except Exception as e:
            logging.error(f"Failed to load config: {e}")

    print("=" * 60)
    print("  JARVIS MONITORING DASHBOARD")
    print("=" * 60)
    print(f"  Port: {port}")
    print(f"  Data Dir: {args.data_dir}")
    print(f"  Config Dir: {args.config_dir}")
    print("=" * 60)
    print()

    try:
        from core.monitoring.unified_dashboard import start_dashboard

        runner = await start_dashboard(
            port=port,
            data_dir=args.data_dir,
            config_dir=args.config_dir,
        )

        print(f"Dashboard running at http://localhost:{port}")
        print("Press Ctrl+C to stop")
        print()

        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
    except Exception as e:
        logging.error(f"Dashboard error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
