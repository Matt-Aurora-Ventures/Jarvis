#!/usr/bin/env python3
"""Start standalone Vanguard control board (API + UI)."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
import os

from core.jupiter_perps.control_board import ControlBoardConfig, create_control_board_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Vanguard control board")
    parser.add_argument("--host", default=os.environ.get("VANGUARD_CONTROL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("VANGUARD_CONTROL_PORT", "8181")))
    parser.add_argument("--runtime-dir", default=os.environ.get("JARVIS_RALPH_RUNTIME_DIR", ""))
    parser.add_argument("--control-state-path", default=os.environ.get("PERPS_CONTROL_STATE_PATH", ""))
    args = parser.parse_args()

    if args.runtime_dir:
        os.environ["JARVIS_RALPH_RUNTIME_DIR"] = args.runtime_dir
    if args.control_state_path:
        os.environ["PERPS_CONTROL_STATE_PATH"] = args.control_state_path

    cfg = ControlBoardConfig.from_env()
    cfg = replace(cfg, host=args.host, port=args.port)

    app = create_control_board_app(cfg)
    try:
        from aiohttp import web
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("aiohttp is required: pip install aiohttp") from exc

    web.run_app(app, host=cfg.host, port=cfg.port)


if __name__ == "__main__":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) if os.name == "nt" else None
    main()
