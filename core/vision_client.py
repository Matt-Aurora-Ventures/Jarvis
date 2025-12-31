"""Vision client with local OCR fallback and optional remote VLM server."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from core import config

ROOT = Path(__file__).resolve().parents[1]
SCREENSHOT_DIR = ROOT / "data" / "screens"


def _capture_screen(path: Optional[Path] = None) -> Optional[str]:
    try:
        import pyautogui
    except Exception:
        return None

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    if path is None:
        filename = f"screen_{int(time.time())}.png"
        path = SCREENSHOT_DIR / filename
    try:
        image = pyautogui.screenshot()
        image.save(str(path))
        return str(path)
    except Exception:
        return None


def _vision_config(cfg: Optional[dict]) -> dict:
    cfg = cfg or config.load_config()
    return cfg.get("vision", {})


def analyze_screen(
    question: str,
    image_path: Optional[str] = None,
    cfg: Optional[dict] = None,
) -> Dict[str, Any]:
    question = (question or "").strip()
    if not question:
        return {"error": "question_required"}

    if not image_path:
        image_path = _capture_screen()
        if not image_path:
            return {"error": "screenshot_failed"}

    vision_cfg = _vision_config(cfg)
    if vision_cfg.get("enabled") and vision_cfg.get("base_url"):
        try:
            with open(image_path, "rb") as handle:
                files = {"image": handle}
                data = {"question": question}
                response = requests.post(
                    f"{vision_cfg['base_url'].rstrip('/')}/analyze",
                    files=files,
                    data=data,
                    timeout=vision_cfg.get("timeout", 30),
                )
            if response.ok:
                payload = response.json()
                return {
                    "source": "vision_server",
                    "image_path": image_path,
                    "answer": payload,
                }
            return {
                "source": "vision_server",
                "image_path": image_path,
                "error": f"http_{response.status_code}",
            }
        except Exception as exc:
            return {
                "source": "vision_server",
                "image_path": image_path,
                "error": str(exc),
            }

    # Local OCR fallback
    try:
        from PIL import Image
    except Exception:
        return {"source": "ocr", "image_path": image_path, "error": "pillow_missing"}

    try:
        import pytesseract
    except Exception:
        return {"source": "ocr", "image_path": image_path, "error": "pytesseract_missing"}

    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image)
        return {
            "source": "ocr",
            "image_path": image_path,
            "answer": text.strip(),
        }
    except Exception as exc:
        return {
            "source": "ocr",
            "image_path": image_path,
            "error": str(exc),
        }
