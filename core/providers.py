import json
import re
import sys
import time
import urllib.request
import warnings
from typing import Optional

from core import config, secrets


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _safe_error_message(exc: Exception, limit: int = 300) -> str:
    msg = str(exc).replace("\n", " ").strip()
    if not msg:
        return exc.__class__.__name__
    if len(msg) <= limit:
        return msg
    return msg[: max(0, limit - 3)] + "..."


_RETRY_IN_RE = re.compile(r"retry in ([0-9.]+)s", re.IGNORECASE)


def _retry_delay_seconds(exc: Exception, attempt: int) -> float:
    match = _RETRY_IN_RE.search(str(exc))
    if match:
        try:
            seconds = float(match.group(1))
            return max(0.1, min(seconds, 30.0))
        except Exception:
            pass
    return min(2.0 * (2**attempt), 8.0)


def _retryable_gemini_error(exc: Exception) -> bool:
    name = exc.__class__.__name__
    if name in {"ResourceExhausted", "TooManyRequests", "ServiceUnavailable", "DeadlineExceeded"}:
        return True
    if isinstance(exc, RuntimeError) and str(exc).startswith("Empty Gemini response"):
        return True
    return False


def _extract_gemini_text(response) -> str:
    try:
        text = response.text or ""
        if text.strip():
            return str(text)
    except Exception:
        pass
    try:
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            collected = []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    collected.append(str(part_text))
            joined = "".join(collected).strip()
            if joined:
                return joined
    except Exception:
        pass
    return ""


_LAST_GEMINI_ERROR: Optional[str] = None
_LAST_OLLAMA_ERROR: Optional[str] = None


def last_provider_errors() -> dict:
    return {
        "gemini": _LAST_GEMINI_ERROR or "",
        "ollama": _LAST_OLLAMA_ERROR or "",
    }


def _gemini_client():
    key = secrets.get_gemini_key()
    if not key:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            import google.generativeai as genai
    except Exception:
        return None
    try:
        genai.configure(api_key=key)
        return genai
    except Exception:
        return None


def _openai_client():
    key = secrets.get_openai_key()
    if not key:
        return None
    try:
        from openai import OpenAI
    except Exception:
        return None
    try:
        return OpenAI(api_key=key)
    except Exception:
        return None


def _gemini_model_name(cfg: dict) -> str:
    raw_name = str(
        cfg.get("providers", {}).get("gemini", {}).get("model", "gemini-flash-latest")
    ).strip()
    if raw_name.startswith("models/"):
        raw_name = raw_name[len("models/") :]
    aliases = {
        "gemini-1.5-flash": "gemini-flash-latest",
        "gemini-1.5-flash-latest": "gemini-flash-latest",
        "gemini-1.5-pro": "gemini-pro-latest",
        "gemini-1.5-pro-latest": "gemini-pro-latest",
    }
    return aliases.get(raw_name, raw_name)


def _openai_model_name(cfg: dict) -> str:
    return cfg.get("providers", {}).get("openai", {}).get("model", "gpt-4o-mini")


def _ollama_model_name(cfg: dict) -> str:
    return cfg.get("providers", {}).get("ollama", {}).get("model", "llama3.2:3b")


def _ollama_base_url(cfg: dict) -> str:
    base_url = cfg.get("providers", {}).get("ollama", {}).get(
        "base_url", "http://localhost:11434"
    )
    return str(base_url).rstrip("/")


def _ollama_enabled(cfg: dict) -> bool:
    return bool(cfg.get("providers", {}).get("ollama", {}).get("enabled", False))


def _ollama_generate_raw(
    base_url: str, model: str, prompt: str, max_output_tokens: int
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_output_tokens},
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    result = json.loads(body)
    text = result.get("response", "")
    if not text:
        raise RuntimeError("Empty response from Ollama")
    return text


def _ollama_generate(prompt: str, max_output_tokens: int) -> Optional[str]:
    cfg = config.load_config()
    if not _ollama_enabled(cfg):
        return None
    base_url = _ollama_base_url(cfg)
    if not base_url:
        return None
    try:
        return _ollama_generate_raw(
            base_url=base_url,
            model=_ollama_model_name(cfg),
            prompt=prompt,
            max_output_tokens=max_output_tokens,
        )
    except Exception:
        return None


def ask_ollama(prompt: str, max_output_tokens: int = 512, cfg: Optional[dict] = None) -> str:
    cfg = cfg or config.load_config()
    if not _ollama_enabled(cfg):
        raise RuntimeError("Ollama is disabled in config")
    base_url = _ollama_base_url(cfg)
    if not base_url:
        raise RuntimeError("Ollama base_url is not configured")
    return _ollama_generate_raw(
        base_url=base_url,
        model=_ollama_model_name(cfg),
        prompt=prompt,
        max_output_tokens=max_output_tokens,
    )


def provider_status() -> dict:
    cfg = config.load_config()
    gemini_enabled = cfg.get("providers", {}).get("gemini", {}).get("enabled", True)
    openai_enabled = cfg.get("providers", {}).get("openai", {}).get("enabled", "auto")
    ollama_enabled = _ollama_enabled(cfg)
    return {
        "gemini_available": bool(_gemini_client()) and bool(gemini_enabled),
        "openai_available": bool(_openai_client())
        and (openai_enabled in (True, "auto")),
        "ollama_available": bool(ollama_enabled),
    }


def ask_gemini(prompt: str, max_output_tokens: int = 512, cfg: Optional[dict] = None) -> str:
    cfg = cfg or config.load_config()
    if not cfg.get("providers", {}).get("gemini", {}).get("enabled", True):
        raise RuntimeError("Gemini is disabled in config")
    client = _gemini_client()
    if not client:
        raise RuntimeError("Gemini client unavailable (missing key or dependency)")
    model = client.GenerativeModel(_gemini_model_name(cfg))
    last_exc: Optional[Exception] = None
    total_wait = 0.0
    for attempt in range(4):
        try:
            response = model.generate_content(
                prompt,
                generation_config={"max_output_tokens": max_output_tokens},
                request_options={"timeout": 30},
            )
            text = _extract_gemini_text(response).strip()
            if text:
                return text
            finish_reason = None
            try:
                candidates = getattr(response, "candidates", None) or []
                if candidates:
                    finish_reason = getattr(candidates[0], "finish_reason", None)
            except Exception:
                finish_reason = None
            if finish_reason is not None:
                raise RuntimeError(f"Empty Gemini response (finish_reason={finish_reason})")
            raise RuntimeError("Empty Gemini response")
        except Exception as exc:
            last_exc = exc
            if attempt < 3 and _retryable_gemini_error(exc):
                delay = _retry_delay_seconds(exc, attempt)
                if total_wait + delay > 45.0:
                    raise
                _log(f"Gemini retrying in {delay:.1f}s...")
                time.sleep(delay)
                total_wait += delay
                continue
            raise
    raise RuntimeError(_safe_error_message(last_exc or RuntimeError("Gemini failed")))


def ask_jarvis(prompt: str, max_output_tokens: int = 512) -> Optional[str]:
    global _LAST_GEMINI_ERROR, _LAST_OLLAMA_ERROR
    cfg = config.load_config()
    try:
        text = ask_gemini(prompt, max_output_tokens=max_output_tokens, cfg=cfg)
        _LAST_GEMINI_ERROR = None
        _LAST_OLLAMA_ERROR = None
        _log(f"Jarvis (Cloud): {_gemini_model_name(cfg)}")
        return text
    except Exception as exc:
        _log("Switching to Local Backup...")
        _LAST_GEMINI_ERROR = f"{exc.__class__.__name__}: {_safe_error_message(exc)}"
        _log(f"Gemini error: {_LAST_GEMINI_ERROR}")
        try:
            text = ask_ollama(prompt, max_output_tokens=max_output_tokens, cfg=cfg)
            _LAST_OLLAMA_ERROR = None
            _log(f"Jarvis (Local): {_ollama_model_name(cfg)}")
            return text
        except Exception as ollama_exc:
            _LAST_OLLAMA_ERROR = (
                f"{ollama_exc.__class__.__name__}: {_safe_error_message(ollama_exc)}"
            )
            _log(f"Ollama error: {_LAST_OLLAMA_ERROR}")
            return None


def generate_text(prompt: str, max_output_tokens: int = 512) -> Optional[str]:
    cfg = config.load_config()
    status = provider_status()

    if status["gemini_available"] or status["ollama_available"]:
        text = ask_jarvis(prompt, max_output_tokens=max_output_tokens)
        if text:
            return text

    if status["openai_available"]:
        client = _openai_client()
        if client:
            try:
                response = client.chat.completions.create(
                    model=_openai_model_name(cfg),
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_output_tokens,
                )
                text = response.choices[0].message.content or ""
                if text:
                    return text
            except Exception:
                pass

    return None
