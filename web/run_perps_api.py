"""Standalone launcher for the Perps API blueprint on port 5001."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from flask import Flask, jsonify
from flask_cors import CORS

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.perps_api import perps_bp  # noqa: E402


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(perps_bp)

    @app.route("/healthz")
    def healthz():
        return jsonify({"ok": True, "service": "perps-api"})

    return app


if __name__ == "__main__":
    from core.logging_utils import configure_component_logger

    configure_component_logger("web.perps", prefix="PERPS_API", level=logging.INFO)
    app = create_app()
    print("Perps API launcher starting on http://127.0.0.1:5001")
    app.run(host="127.0.0.1", port=5001, debug=True)
