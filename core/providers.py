import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import warnings
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Deque, Dict, List, Optional
from collections import deque

import requests
from core import config, secrets, state as state_module

# Trading context injection for backup LLMs
_TRADING_CONTEXT_ENABLED = True  # Enable trading knowledge for all LLMs


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

_GROQ_LOCK = threading.Lock()
_GROQ_MIN_CALL_INTERVAL = 1.0  # seconds
_LAST_GROQ_CALL = 0.0

_OLLAMA_HEALTH: Dict[str, Any] = {
    "base_url": "",
    "available": False,
    "checked_at": 0.0,
    "ttl": 30.0,
}


def _retry_delay_seconds(exc: Exception, attempt: int) -> float:
    match = _RETRY_IN_RE.search(str(exc))
    if match:
        try:
            seconds = float(match.group(1))
            return max(0.1, min(seconds, 30.0))
        except Exception as e:
            pass
    return min(2.0 * (2**attempt), 8.0)


def _retryable_gemini_error(exc: Exception) -> bool:
    name = exc.__class__.__name__
    msg = str(exc).lower()
    
    # Handle quota/limit errors specifically
    if "quota exceeded" in msg or "429" in msg or "rate limit" in msg:
        return True
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
    except Exception as e:
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
    except Exception as e:
        pass
    return ""


@dataclass
class ProviderAttempt:
    provider: str
    provider_type: str
    success: bool
    error: str = ""
    latency_ms: int = 0
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


_LAST_PROVIDER_ERRORS: Dict[str, str] = {"openrouter": "", "gemini": "", "ollama": "", "groq": "", "grok": "", "openai": "", "minimax": ""}
_ATTEMPT_HISTORY: Deque[ProviderAttempt] = deque(maxlen=25)


def _record_attempt(attempt: ProviderAttempt, diagnostics: Optional[List[Dict[str, Any]]] = None) -> None:
    _ATTEMPT_HISTORY.append(attempt)
    if diagnostics is not None:
        diagnostics.append(asdict(attempt))


def _record_success_attempt(
    provider: str,
    provider_type: str,
    start_ts: float,
    metadata: Dict[str, Any],
    diagnostics: Optional[List[Dict[str, Any]]],
) -> None:
    attempt = ProviderAttempt(
        provider=provider,
        provider_type=provider_type,
        success=True,
        error="",
        latency_ms=int((time.time() - start_ts) * 1000),
        timestamp=time.time(),
        metadata=metadata,
    )
    _set_provider_error(provider_type, "")
    _record_attempt(attempt, diagnostics)
    try:
        state_module.update_state(
            last_llm_provider=provider,
            last_llm_model=metadata.get("model", ""),
            last_llm_latency_ms=attempt.latency_ms,
            last_llm_timestamp=time.time(),
        )
    except Exception:
        pass


def last_generation_attempts(limit: int = 10) -> List[Dict[str, Any]]:
    """Return recent provider attempts for debugging."""
    recent = list(_ATTEMPT_HISTORY)[-limit:]
    return [asdict(item) for item in recent]


def _set_provider_error(provider_type: str, message: str) -> None:
    provider_type = provider_type or "unknown"
    _LAST_PROVIDER_ERRORS[provider_type] = message


def last_provider_errors() -> dict:
    return dict(_LAST_PROVIDER_ERRORS)


def _gemini_client():
    key = secrets.get_gemini_key()
    if not key:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            import google.generativeai as genai
    except Exception as e:
        return None
    try:
        genai.configure(api_key=key)
        return genai
    except Exception as e:
        return None


def _openai_client():
    key = secrets.get_openai_key()
    if not key:
        return None
    try:
        from openai import OpenAI
    except Exception as e:
        return None
    try:
        return OpenAI(api_key=key)
    except Exception as e:
        return None


def _gemini_model_name(cfg: dict) -> str:
    raw_name = str(
        cfg.get("providers", {}).get("gemini", {}).get("model", "gemini-2.0-flash-exp")
    ).strip()
    if raw_name.startswith("models/"):
        raw_name = raw_name[len("models/") :]
    # Use only models that actually exist - checked via ListModels
    aliases = {
        "gemini-flash-latest": "gemini-2.5-flash",
        "gemini-2.0-flash": "gemini-2.0-flash",
        "gemini-2.0-flash-exp": "gemini-2.0-flash-exp",
        "gemini-2.5-flash": "gemini-2.5-flash",
        "gemini-2.5-pro": "gemini-2.5-pro",
        "gemini-1.5-flash": "gemini-2.5-flash",  # Redirect old to new
        "gemini-1.5-pro": "gemini-2.5-pro",  # Redirect old to new
        "gemini-pro": "gemini-2.5-flash",
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
    return bool(cfg.get("providers", {}).get("ollama", {}).get("enabled", True))


def _ollama_generate_raw(
    base_url: str, model: str, prompt: str, max_output_tokens: int, timeout: int = 120
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
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    result = json.loads(body)
    text = result.get("response", "")
    if not text:
        raise RuntimeError("Empty response from Ollama")
    return text


def _ollama_generate(
    prompt: str,
    max_output_tokens: int,
    timeout: int = 120,
) -> Optional[str]:
    cfg = config.load_config()
    if not _ollama_enabled(cfg):
        return None
    base_url = _ollama_base_url(cfg)
    if not base_url:
        return None
    if not _ollama_available(base_url):
        return None
    try:
        return _ollama_generate_raw(
            base_url=base_url,
            model=_ollama_model_name(cfg),
            prompt=prompt,
            max_output_tokens=max_output_tokens,
            timeout=timeout,
        )
    except Exception as e:
        return None


def ask_ollama(prompt: str, max_output_tokens: int = 512, cfg: Optional[dict] = None, timeout: int = 180) -> str:
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
        timeout=timeout,
    )


def ask_ollama_model(
    prompt: str,
    model: str,
    max_output_tokens: int = 512,
    cfg: Optional[dict] = None,
    timeout: int = 180,
) -> str:
    cfg = cfg or config.load_config()
    if not _ollama_enabled(cfg):
        raise RuntimeError("Ollama is disabled in config")
    base_url = _ollama_base_url(cfg)
    if not base_url:
        raise RuntimeError("Ollama base_url is not configured")
    model = model.strip()
    if not model:
        raise RuntimeError("Ollama model is empty")
    return _ollama_generate_raw(
        base_url=base_url,
        model=model,
        prompt=prompt,
        max_output_tokens=max_output_tokens,
        timeout=timeout,
    )


def provider_status() -> dict:
    """Get status of all providers including the PRIMARY (OpenRouter/MiniMax)."""
    cfg = config.load_config()
    gemini_enabled = cfg.get("providers", {}).get("gemini", {}).get("enabled", True)
    openai_enabled = cfg.get("providers", {}).get("openai", {}).get("enabled", "auto")
    ollama_enabled = _ollama_enabled(cfg)
    return {
        "openrouter_available": bool(_openrouter_client()),  # PRIMARY
        "groq_available": bool(_groq_client()),
        "grok_available": bool(_grok_client()),
        "ollama_available": bool(ollama_enabled),
        "gemini_available": bool(_gemini_client()) and bool(gemini_enabled),
        "openai_available": bool(_openai_client()) and (openai_enabled in (True, "auto")),
        "minimax_direct_available": bool(secrets.get_minimax_key()),
    }


def provider_health_check() -> dict:
    """Run health check on all providers - used for self-healing diagnostics."""
    status = provider_status()
    ranked = get_ranked_providers(prefer_free=False)
    
    return {
        "primary_provider": ranked[0]["name"] if ranked else None,
        "primary_type": ranked[0]["provider"] if ranked else None,
        "available_providers": [p["name"] for p in ranked],
        "total_available": len(ranked),
        "status": status,
        "last_errors": dict(_LAST_PROVIDER_ERRORS),
        "healthy": len(ranked) >= 2,  # At least 2 providers for redundancy
    }


# Only use models that exist - verified via API
_FREE_TIER_MODELS = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash-exp", "gemini-2.0-flash"]


def ask_gemini(prompt: str, max_output_tokens: int = 512, cfg: Optional[dict] = None) -> str:
    cfg = cfg or config.load_config()
    if not cfg.get("providers", {}).get("gemini", {}).get("enabled", True):
        raise RuntimeError("Gemini is disabled in config")
    client = _gemini_client()
    if not client:
        raise RuntimeError("Gemini client unavailable (missing key or dependency)")

    is_free_tier = cfg.get("providers", {}).get("gemini", {}).get("free_tier", True)
    primary_model = _gemini_model_name(cfg)

    if is_free_tier:
        models_to_try = [primary_model] + [m for m in _FREE_TIER_MODELS if m != primary_model]
    else:
        models_to_try = [primary_model]

    last_exc: Optional[Exception] = None

    for model_name in models_to_try:
        model = client.GenerativeModel(model_name)
        total_wait = 0.0

        for attempt in range(3):
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
                except Exception as e:
                    finish_reason = None
                if finish_reason is not None:
                    raise RuntimeError(f"Empty Gemini response (finish_reason={finish_reason})")
                raise RuntimeError("Empty Gemini response")
            except Exception as exc:
                last_exc = exc
                exc_name = exc.__class__.__name__
                if exc_name in {"ResourceExhausted", "TooManyRequests"}:
                    if attempt < 2:
                        delay = min(5.0 * (attempt + 1), 15.0)
                        if total_wait + delay <= 30.0:
                            _log(f"Gemini {model_name} rate limited, waiting {delay:.0f}s...")
                            time.sleep(delay)
                            total_wait += delay
                            continue
                    _log(f"Gemini {model_name} quota exceeded, trying next model...")
                    break
                if attempt < 2 and _retryable_gemini_error(exc):
                    delay = _retry_delay_seconds(exc, attempt)
                    if total_wait + delay > 30.0:
                        break
                    _log(f"Gemini {model_name} retrying in {delay:.1f}s...")
                    time.sleep(delay)
                    total_wait += delay
                    continue
                break

    raise RuntimeError(_safe_error_message(last_exc or RuntimeError("All Gemini models failed")))


def transcribe_audio_gemini(audio_path: str) -> Optional[str]:
    client = _gemini_client()
    if not client:
        return None
    
    # Debug: Verify key (first 4 chars)
    key = secrets.get_gemini_key()
    if key:
        _log(f"Gemini Key Prefix: {key[:4]}...")

    uploaded_file = None
    try:
        uploaded_file = client.upload_file(audio_path, mime_type="audio/wav")
        
        # Try a list of likely model names
        candidates = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-2.0-flash-exp"]
        
        for model_name in candidates:
            try:
                model = client.GenerativeModel(model_name)
                response = model.generate_content(
                    ["Transcribe this audio exactly. Output only the text.", uploaded_file]
                )
                text = _extract_gemini_text(response)
                if text:
                    try:
                        uploaded_file.delete()
                    except Exception as e:
                        pass
                    return text
            except Exception as inner_e:
                _log(f"Gemini Model {model_name} failed: {_safe_error_message(inner_e)}")
                continue
        
        # If we get here, all models failed
        if uploaded_file:
            try:
                uploaded_file.delete()
            except Exception:
                pass
        return None

    except Exception as e:
        _log(f"Gemini STT Error: {_safe_error_message(e)}")
        if uploaded_file:
            try:
                uploaded_file.delete()
            except Exception:
                pass
        return None


# === INTELLIGENT PROVIDER RANKING ===
# Ranked by: Intelligence, Free tier availability, Resource efficiency
# Priority: OpenRouter/MiniMax (PRIMARY) → Groq (backup) → Ollama (local fallback)
# Updated Jan 2026: MiniMax 2.1 via OpenRouter as default conversational engine

PROVIDER_RANKINGS = [
    # Rank 0: OpenRouter with MiniMax 2.1 (PRIMARY - default for voice/chat)
    {"name": "minimax/minimax-01", "provider": "openrouter", "intelligence": 96, "free": False, "notes": "PRIMARY - MiniMax 2.1 via OpenRouter"},
    
    # Rank 1: OpenRouter alternatives (if MiniMax fails)
    {"name": "deepseek/deepseek-r1", "provider": "openrouter", "intelligence": 95, "free": False, "notes": "DeepSeek R1 reasoning fallback"},
    {"name": "google/gemini-2.0-flash-exp:free", "provider": "openrouter", "intelligence": 92, "free": True, "notes": "OpenRouter free Gemini 2.0"},
    {"name": "meta-llama/llama-3.3-70b-instruct", "provider": "openrouter", "intelligence": 90, "free": False, "notes": "Llama 3.3 70B via OpenRouter"},
    
    # Rank 2: Groq (BACKUP - fast, free, but rate limited)
    {"name": "llama-3.3-70b-versatile", "provider": "groq", "intelligence": 90, "free": True, "notes": "Groq ultra fast (rate limited)"},
    {"name": "llama-3.1-8b-instant", "provider": "groq", "intelligence": 78, "free": True, "notes": "Groq 8B instant fallback"},

    # Rank 3: Grok (X.AI - for sentiment analysis when needed)
    {"name": "grok-beta", "provider": "grok", "intelligence": 92, "free": False, "notes": "Grok - X.com sentiment analysis"},
    {"name": "grok-2-latest", "provider": "grok", "intelligence": 95, "free": False, "notes": "Grok 2 - advanced reasoning"},

    # Rank 4: Local Ollama (FALLBACK - always available offline)
    {"name": "llama3.1:8b", "provider": "ollama", "intelligence": 78, "free": True, "notes": "Local 8B - offline fallback"},
    {"name": "qwen2.5:1.5b", "provider": "ollama", "intelligence": 65, "free": True, "notes": "Fast lightweight local"},

    # Rank 5: Native MiniMax (if direct key configured)
    {"name": "minimax-latest", "provider": "minimax", "intelligence": 96, "free": False, "notes": "Direct MiniMax API"},

    # Rank 6: Gemini (disabled by default due to quota issues)
    {"name": "gemini-cli", "provider": "gemini-cli", "intelligence": 95, "free": True, "notes": "Gemini CLI - needs credits"},
    {"name": "gemini-2.5-flash", "provider": "gemini", "intelligence": 92, "free": True, "notes": "May fail without credits"},
    {"name": "gemini-2.5-pro", "provider": "gemini", "intelligence": 95, "free": True, "notes": "May fail without credits"},

    # Rank 7: Paid fallbacks (only if all else fails)
    {"name": "gpt-4o-mini", "provider": "openai", "intelligence": 88, "free": False, "notes": "Paid fallback"},
]


def _gemini_cli_available() -> bool:
    """Check if Gemini CLI is installed and configured."""
    return shutil.which("gemini") is not None


def _ask_gemini_cli(prompt: str, max_output_tokens: int = 512) -> Optional[str]:
    """Use Gemini CLI to generate text."""
    # Set up environment with API key
    env = dict(os.environ)
    key = secrets.get_gemini_key()
    if key:
        env["GEMINI_API_KEY"] = key
    
    try:
        result = subprocess.run(
            ["gemini", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except Exception:
        return None


def validate_groq_api_key() -> tuple[bool, str]:
    """Validate Groq API key with clear error messages.

    Returns:
        Tuple of (is_valid, message)
    """
    key = os.environ.get("GROQ_API_KEY") or secrets.get_groq_key()

    if not key:
        return False, (
            "❌ GROQ_API_KEY not configured!\n"
            "Groq is the primary LLM provider (free, fast).\n\n"
            "To fix:\n"
            "  1. Get free key at: https://console.groq.com\n"
            "  2. Set: export GROQ_API_KEY='gsk_your_key'\n"
            "  3. Or add to secrets/keys.json: {\"groq_api_key\": \"gsk_...\"}\n\n"
            "System will fall back to slower alternatives."
        )

    if not key.startswith("gsk_"):
        return False, (
            "⚠️ GROQ_API_KEY format invalid!\n"
            "Groq keys should start with 'gsk_'\n"
            f"Got: {key[:8]}...\n\n"
            "Get a valid key at: https://console.groq.com"
        )

    return True, "✓ Groq API key configured"


def _groq_client():
    """Get Groq client if available."""
    key = os.environ.get("GROQ_API_KEY") or secrets.get_groq_key()
    if not key:
        # Log warning instead of silent failure
        valid, msg = validate_groq_api_key()
        if not valid:
            logger.warning(msg.replace("\n", " | "))
        return None
    try:
        from groq import Groq
        return Groq(api_key=key)
    except ImportError:
        logger.warning("Groq package not installed. Run: pip install groq")
    except Exception as e:
        logger.warning(f"Groq client init failed: {e}")
    return {"api_key": key}  # Fallback handled in _ask_groq


def _grok_client():
    """Get X.AI Grok client if available."""
    key = os.environ.get("XAI_API_KEY") or secrets.get_grok_key()
    if not key:
        return None
    # X.AI uses OpenAI-compatible API, so we can use the OpenAI client
    try:
        from openai import OpenAI
        return OpenAI(
            api_key=key,
            base_url="https://api.x.ai/v1"
        )
    except ImportError:
        pass
    except Exception:
        pass
    return {"api_key": key}  # Fallback handled in _ask_grok


def _ask_minimax(prompt: str, model: str, max_output_tokens: int = 2048) -> Optional[str]:
    """Call MiniMax API directly."""
    api_key = secrets.get_minimax_key()
    if not api_key:
        return None

    # MiniMax API endpoint (Abab6.5 assumed for M2.1 equivalent)
    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    
    # Map friendly names to actual MiniMax model IDs if needed
    if model in ("minimax-2.1", "minimax-latest", "minimax"):
        model = "abab6.5-chat"

    messages = [{"sender_type": "USER", "sender_name": "User", "text": prompt}]

    payload = {
        "model": model,
        "messages": messages,
        "tokens_to_generate": max_output_tokens,
        "temperature": 0.7,
        "stream": False,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        
        # Handle rate limits
        if response.status_code == 429:
             _log("⚠ MiniMax rate limited (429).")
             return None
             
        response.raise_for_status()
        body = response.json()
        
        choices = body.get("choices", [])
        if choices:
            text = choices[0].get("message", {}).get("text", "")
            if not text:
                 text = choices[0].get("text", "") # Fallback
            return text
            
        if "base_resp" in body and body["base_resp"].get("status_msg"):
             _log(f"⚠ MiniMax Error: {body['base_resp']['status_msg']}")
             
    except Exception as e:
        _log(f"⚠ MiniMax call failed: {_safe_error_message(e)}")
        
    return None


def _openrouter_client():
    """Get OpenRouter API key if available."""
    key = os.environ.get("OPENROUTER_API_KEY") or secrets.get_openrouter_key()
    if not key:
        return None
    return {"api_key": key}


def _ask_openrouter(prompt: str, model: str, max_output_tokens: int = 2048) -> Optional[str]:
    """Call OpenRouter API - supports MiniMax, DeepSeek, Llama, etc.
    
    OpenRouter is the PRIMARY provider because:
    - No rate limits with credits
    - Access to MiniMax 2.1 (minimax/minimax-01)
    - High quality, low cost
    - Self-healing: automatic fallback to other models
    """
    client = _openrouter_client()
    if not client:
        return None
    
    api_key = client["api_key"]
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/lifeos",
        "X-Title": "LifeOS Jarvis",
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_output_tokens,
        "temperature": 0.7,
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=120)
        
        if response.status_code == 429:
            _log("⚠ OpenRouter rate limited (429)")
            return None
        if response.status_code == 402:
            _log("⚠ OpenRouter insufficient credits (402)")
            return None
            
        response.raise_for_status()
        body = response.json()
        
        choices = body.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            text = message.get("content", "")
            if text:
                return text.strip()
                
        # Check for error
        if "error" in body:
            _log(f"⚠ OpenRouter error: {body['error']}")
            
    except requests.exceptions.Timeout:
        _log("⚠ OpenRouter timeout")
    except Exception as e:
        _log(f"⚠ OpenRouter call failed: {_safe_error_message(e)}")
        
    return None


def _ask_groq(prompt: str, model: str, max_output_tokens: int = 512) -> Optional[str]:
    """Use Groq for ultra-fast inference."""
    client = _groq_client()
    if client is None:
        return None
    
    # If actual Groq SDK is available, client will have chat attribute
    if hasattr(client, "chat"):
        with _throttled_groq_call():
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_output_tokens,
                    temperature=0.7,
                )
                return response.choices[0].message.content
            except Exception as exc:
                _log(f"⚠ Groq SDK call failed: {_safe_error_message(exc)}")
                pass
    
    # HTTP fallback (works without groq SDK)
    with _throttled_groq_call():
        try:
            api_key = (
                client.get("api_key")
                if isinstance(client, dict)
                else os.environ.get("GROQ_API_KEY") or secrets.get_groq_key()
            )
            if not api_key:
                return None
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_output_tokens,
                "temperature": 0.7,
            }
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            if response.status_code == 429:
                _log("⚠ Groq rate limited (429). Backing off for 3s.")
                time.sleep(3)
                return None
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0]["message"]["content"]
        except Exception as exc:
            _log(f"⚠ Groq HTTP call failed: {_safe_error_message(exc)}")
            return None


def _throttled_groq_call():
    """Context manager to serialize Groq calls and honor minimum spacing."""
    class _GroqThrottle:
        def __enter__(self_inner):
            global _LAST_GROQ_CALL
            with _GROQ_LOCK:
                now = time.time()
                wait = _GROQ_MIN_CALL_INTERVAL - (now - _LAST_GROQ_CALL)
                if wait > 0:
                    time.sleep(wait)
                _LAST_GROQ_CALL = time.time()
            return self_inner

        def __exit__(self_inner, exc_type, exc, tb):
            return False

    return _GroqThrottle()


def _ask_grok(prompt: str, model: str, max_output_tokens: int = 512) -> Optional[str]:
    """Use X.AI Grok for inference with sentiment analysis capabilities."""
    client = _grok_client()
    if client is None:
        return None

    # If actual OpenAI client is available (X.AI uses OpenAI-compatible API)
    if hasattr(client, "chat"):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_output_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as exc:
            _log(f"⚠ Grok SDK call failed: {_safe_error_message(exc)}")
            return None

    # HTTP fallback for X.AI API
    try:
        api_key = (
            client.get("api_key")
            if isinstance(client, dict)
            else os.environ.get("XAI_API_KEY") or secrets.get_grok_key()
        )
        if not api_key:
            return None
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output_tokens,
            "temperature": 0.7,
        }
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if response.status_code == 429:
            _log("⚠ Grok rate limited (429). Backing off for 3s.")
            time.sleep(3)
            return None
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0]["message"]["content"]
    except Exception as exc:
        _log(f"⚠ Grok HTTP call failed: {_safe_error_message(exc)}")
        return None


def _ollama_available(base_url: str) -> bool:
    ttl = _OLLAMA_HEALTH["ttl"]
    now = time.time()
    if (
        _OLLAMA_HEALTH["base_url"] == base_url
        and now - _OLLAMA_HEALTH["checked_at"] < ttl
    ):
        return _OLLAMA_HEALTH["available"]

    try:
        request = urllib.request.Request(f"{base_url}/api/tags", method="GET")
        with urllib.request.urlopen(request, timeout=3) as response:
            available = response.status == 200
    except Exception:
        available = False

    _OLLAMA_HEALTH.update(
        {"base_url": base_url, "available": available, "checked_at": now}
    )
    if not available:
        _log(f"⚠ Ollama at {base_url} unavailable; skipping local fallback.")
    return available

def get_ranked_providers(prefer_free: bool = True) -> list:
    """Get providers ranked by intelligence, with free models first if preferred.
    
    Priority order:
    1. OpenRouter (MiniMax 2.1 PRIMARY) - no rate limits with credits
    2. Groq (backup) - fast but rate limited
    3. Ollama (local fallback) - always available offline
    """
    cfg = config.load_config()
    available = []

    for provider in PROVIDER_RANKINGS:
        if provider["provider"] == "openrouter":
            # OpenRouter is PRIMARY if key is available
            if _openrouter_client():
                available.append(provider)
        elif provider["provider"] == "gemini-cli":
            # Disable Gemini-cli due to quota issues
            if False and _gemini_cli_available():
                available.append(provider)
        elif provider["provider"] == "gemini":
            # Disable Gemini due to quota issues
            if False and _gemini_client() and cfg.get("providers", {}).get("gemini", {}).get("enabled", False):
                available.append(provider)
        elif provider["provider"] == "groq":
            if _groq_client():
                available.append(provider)
        elif provider["provider"] == "grok":
            if _grok_client() and cfg.get("providers", {}).get("grok", {}).get("enabled", False):
                available.append(provider)
        elif provider["provider"] == "ollama":
            if _ollama_enabled(cfg):
                available.append(provider)
        elif provider["provider"] == "minimax":
            if secrets.get_minimax_key():
                available.append(provider)
        elif provider["provider"] == "openai":
            if _openai_client() and cfg.get("providers", {}).get("openai", {}).get("enabled", "auto") != False:
                available.append(provider)

    if prefer_free:
        # Sort: free first, then by intelligence
        available.sort(key=lambda x: (not x["free"], -x["intelligence"]))
    else:
        # Sort purely by intelligence
        available.sort(key=lambda x: -x["intelligence"])

    return available


def _apply_routing_override(available: List[Dict[str, Any]], cfg: dict) -> List[Dict[str, Any]]:
    override_model = os.environ.get("LIFEOS_MODEL_OVERRIDE") or cfg.get("router", {}).get("override_model")
    override_provider = os.environ.get("LIFEOS_PROVIDER_OVERRIDE") or cfg.get("router", {}).get("override_provider")
    if not override_model and not override_provider:
        return available

    def _matches(entry: Dict[str, Any]) -> bool:
        if override_model and entry.get("name") != override_model:
            return False
        if override_provider and entry.get("provider") != override_provider:
            return False
        return True

    override = None
    for entry in available:
        if _matches(entry):
            override = entry
            break
    if not override:
        return available

    reordered = [override] + [entry for entry in available if entry is not override]
    return reordered


def _try_provider(
    provider: dict,
    prompt: str,
    max_output_tokens: int,
    cfg: dict,
    diagnostics: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """Try a single provider and return result or None."""
    name = provider["name"]
    ptype = provider["provider"]
    start_ts = time.time()
    metadata = {
        "model": name,
        "intelligence": provider.get("intelligence"),
        "free": provider.get("free", False),
        "notes": provider.get("notes", ""),
    }
    success_log: Optional[str] = None
    text: Optional[str] = None
    error_message = ""

    try:
        if ptype == "gemini-cli":
            text = _ask_gemini_cli(prompt, max_output_tokens)
            if text:
                success_log = f"✓ Using Gemini CLI (intelligence: {provider['intelligence']})"

        elif ptype == "groq":
            text = _ask_groq(prompt, name, max_output_tokens)
            if text:
                success_log = f"✓ Using Groq {name} (intelligence: {provider['intelligence']}) - FAST"

        elif ptype == "openrouter":
            text = _ask_openrouter(prompt, name, max_output_tokens)
            if text:
                success_log = f"✓ Using OpenRouter {name} (intelligence: {provider['intelligence']}) - PRIMARY"

        elif ptype == "grok":
            text = _ask_grok(prompt, name, max_output_tokens)
            if text:
                success_log = f"✓ Using Grok {name} (intelligence: {provider['intelligence']}) - X.AI sentiment"

        elif ptype == "gemini":
            # Use specific model
            client = _gemini_client()
            if not client:
                error_message = "Gemini client unavailable"
            else:
                model = client.GenerativeModel(name)
                response = model.generate_content(
                    prompt,
                    generation_config={"max_output_tokens": max_output_tokens},
                    request_options={"timeout": 60},
                )
                text = _extract_gemini_text(response).strip()
                if text:
                    success_log = f"✓ Using {name} (intelligence: {provider['intelligence']})"

        elif ptype == "ollama":
            base_url = _ollama_base_url(cfg)
            if not base_url:
                error_message = "Ollama base_url not configured"
            else:
                text = _ollama_generate_raw(
                    base_url=base_url,
                    model=name,
                    prompt=prompt,
                    max_output_tokens=max_output_tokens,
                    timeout=120,
                )
                if text:
                    success_log = f"✓ Using {name} locally (intelligence: {provider['intelligence']})"

                if text:
                    success_log = f"✓ Using {name} (intelligence: {provider['intelligence']})"

        elif ptype == "minimax":
            text = _ask_minimax(prompt, name, max_output_tokens)
            if text:
                 success_log = f"✓ Using MiniMax {name} (intelligence: {provider['intelligence']}) - DIRECT"
                 
        elif ptype == "openai":
            client = _openai_client()
            if not client:
                error_message = "OpenAI client unavailable"
            else:
                response = client.chat.completions.create(
                    model=name,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_output_tokens,
                )
                text = response.choices[0].message.content or ""
                if text:
                    success_log = f"✓ Using {name} (intelligence: {provider['intelligence']})"

    except Exception as e:
        error_message = _safe_error_message(e)
        error_name = e.__class__.__name__
        if error_name in ("ResourceExhausted", "RateLimitError"):
            _log(f"⚠ {name} rate limited, trying next... ({error_message})")
        else:
            _log(f"⚠ {name} failed: {error_message}")
    else:
        if text:
            if success_log:
                _log(success_log)
            _record_success_attempt(name, ptype, start_ts, metadata, diagnostics)
            return text
        if not error_message:
            error_message = "Empty response"

    attempt = ProviderAttempt(
        provider=name,
        provider_type=ptype,
        success=False,
        error=error_message,
        latency_ms=int((time.time() - start_ts) * 1000),
        timestamp=time.time(),
        metadata=metadata,
    )
    _set_provider_error(ptype, error_message)
    _record_attempt(attempt, diagnostics)
    return None


def generate_text(
    prompt: str,
    max_output_tokens: int = 512,
    prefer_free: bool = True,
    diagnostics: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """Generate text using the best available provider, ranked by intelligence.
    
    Priority order:
    1. Best free cloud models (Gemini 2.5 Pro/Flash)
    2. Local models (Ollama - always available, private)
    3. Paid fallbacks (OpenAI - only if free exhausted)
    
    This ensures we use the most intelligent, free resources first.
    """
    cfg = config.load_config()
    ranked = get_ranked_providers(prefer_free=prefer_free)
    ranked = _apply_routing_override(ranked, cfg)
    
    if not ranked:
        _log("No AI providers available")
        return None
    
    _log(f"Provider chain: {' → '.join(p['name'] for p in ranked[:4])}")
    
    for provider in ranked:
        result = _try_provider(
            provider,
            prompt,
            max_output_tokens,
            cfg,
            diagnostics=diagnostics,
        )
        if result:
            return result
    
    _log("All providers exhausted")
    return None


def generate_text_with_trading(
    prompt: str,
    max_output_tokens: int = 512,
    prefer_free: bool = True,
    include_positions: bool = True,
    diagnostics: Optional[List[Dict[str, Any]]] = None,
) -> Optional[str]:
    """Generate text with full trading context injected.
    
    This teaches backup LLMs (Groq, Ollama) about the trading system
    so they can answer trading questions intelligently.
    
    Args:
        prompt: User's prompt
        max_output_tokens: Max response tokens
        prefer_free: Prefer free providers
        include_positions: Include current position data
        diagnostics: Optional diagnostics list
        
    Returns:
        Generated text with trading awareness
    """
    if not _TRADING_CONTEXT_ENABLED:
        return generate_text(prompt, max_output_tokens, prefer_free, diagnostics)
    
    try:
        from core.trading_knowledge import inject_trading_context
        enhanced_prompt = inject_trading_context(prompt, include_positions=include_positions)
        # Increase token budget for context
        adjusted_tokens = min(max_output_tokens + 200, 2048)
        return generate_text(enhanced_prompt, adjusted_tokens, prefer_free, diagnostics)
    except ImportError:
        _log("Trading knowledge module not available, using base prompt")
        return generate_text(prompt, max_output_tokens, prefer_free, diagnostics)
    except Exception as e:
        _log(f"Trading context injection failed: {e}")
        return generate_text(prompt, max_output_tokens, prefer_free, diagnostics)


def ask_jarvis(prompt: str, max_output_tokens: int = 512) -> Optional[str]:
    """Legacy function - now uses smart ranking."""
    return generate_text(prompt, max_output_tokens=max_output_tokens, prefer_free=True)


def ask_jarvis_trading(prompt: str, max_output_tokens: int = 1024) -> Optional[str]:
    """Ask Jarvis with full trading context - use for trading questions."""
    return generate_text_with_trading(
        prompt, 
        max_output_tokens=max_output_tokens, 
        prefer_free=True,
        include_positions=True
    )


def check_provider_health() -> Dict[str, Dict[str, Any]]:
    """Check health of all AI providers with actionable diagnostics.

    Returns dict like:
    {
        "groq": {"available": True, "status": "ok", "message": "Ready"},
        "ollama": {"available": False, "status": "error", "message": "Not running at localhost:11434"},
        ...
    }
    """
    cfg = config.load_config()
    results = {}

    # Check Groq
    groq_key = secrets.get_groq_key()
    if groq_key:
        client = _groq_client()
        if client:
            results["groq"] = {
                "available": True,
                "status": "ok",
                "message": "Ready (primary provider)",
                "fix": None,
            }
        else:
            results["groq"] = {
                "available": False,
                "status": "error",
                "message": "Key set but client failed to initialize",
                "fix": "pip install groq",
            }
    else:
        results["groq"] = {
            "available": False,
            "status": "missing_key",
            "message": "API key not configured (PRIMARY provider - should be set)",
            "fix": "export GROQ_API_KEY='your-key' or add groq_api_key to secrets/keys.json",
        }

    # Check Grok (X.AI)
    grok_key = secrets.get_grok_key()
    grok_enabled = cfg.get("providers", {}).get("grok", {}).get("enabled", False)
    if grok_key and grok_enabled:
        client = _grok_client()
        if client:
            results["grok"] = {
                "available": True,
                "status": "ok",
                "message": "Ready (X.AI Grok - sentiment analysis, paid)",
                "fix": None,
            }
        else:
            results["grok"] = {
                "available": False,
                "status": "error",
                "message": "Key set but client failed",
                "fix": "Check XAI_API_KEY or pip install openai",
            }
    elif grok_key and not grok_enabled:
        results["grok"] = {
            "available": False,
            "status": "disabled",
            "message": "Key configured but provider disabled",
            "fix": "Set providers.grok.enabled=true in lifeos.config.json",
        }
    else:
        results["grok"] = {
            "available": False,
            "status": "not_configured",
            "message": "Not configured (optional - sentiment analysis, paid)",
            "fix": "export XAI_API_KEY='your-key' and enable in config (optional)",
        }

    # Check Ollama
    ollama_enabled = _ollama_enabled(cfg)
    if ollama_enabled:
        base_url = _ollama_base_url(cfg)
        try:
            request = urllib.request.Request(f"{base_url}/api/tags", method="GET")
            with urllib.request.urlopen(request, timeout=5) as response:
                if response.status == 200:
                    results["ollama"] = {
                        "available": True,
                        "status": "ok",
                        "message": f"Running at {base_url}",
                        "fix": None,
                    }
                else:
                    results["ollama"] = {
                        "available": False,
                        "status": "error",
                        "message": f"Unexpected response from {base_url}",
                        "fix": "Check Ollama logs",
                    }
        except Exception as e:
            results["ollama"] = {
                "available": False,
                "status": "not_running",
                "message": f"Cannot reach {base_url}",
                "fix": "Run: ollama serve (or install from ollama.ai)",
            }
    else:
        results["ollama"] = {
            "available": False,
            "status": "disabled",
            "message": "Disabled in config",
            "fix": "Set providers.ollama.enabled=true in config",
        }

    # Check Gemini (currently disabled in code)
    gemini_key = secrets.get_gemini_key()
    gemini_enabled = cfg.get("providers", {}).get("gemini", {}).get("enabled", False)
    if gemini_key and gemini_enabled:
        client = _gemini_client()
        if client:
            results["gemini"] = {
                "available": True,
                "status": "ok",
                "message": "Ready (but currently disabled in code due to quota issues)",
                "fix": None,
            }
        else:
            results["gemini"] = {
                "available": False,
                "status": "error",
                "message": "Key set but client failed",
                "fix": "pip install google-generativeai",
            }
    elif gemini_key and not gemini_enabled:
        results["gemini"] = {
            "available": False,
            "status": "disabled",
            "message": "Key configured but provider disabled",
            "fix": "Set providers.gemini.enabled=true (note: has quota issues)",
        }
    else:
        results["gemini"] = {
            "available": False,
            "status": "missing_key",
            "message": "API key not configured",
            "fix": "export GEMINI_API_KEY='your-key' (optional - has quota issues)",
        }

    # Check OpenAI
    openai_key = secrets.get_openai_key()
    openai_enabled = cfg.get("providers", {}).get("openai", {}).get("enabled", "auto")
    if openai_key:
        client = _openai_client()
        if client:
            results["openai"] = {
                "available": True,
                "status": "ok",
                "message": "Ready (paid fallback - will be charged)",
                "fix": None,
            }
        else:
            results["openai"] = {
                "available": False,
                "status": "error",
                "message": "Key set but client failed",
                "fix": "pip install openai",
            }
    else:
        results["openai"] = {
            "available": False,
            "status": "not_configured",
            "message": "Not configured (optional paid fallback)",
            "fix": "export OPENAI_API_KEY='your-key' (optional - costs money)",
        }

    return results


def get_provider_summary() -> str:
    """Get human-readable provider status summary."""
    health = check_provider_health()
    lines = ["Provider Status:"]

    for name, info in health.items():
        status_icon = "✓" if info["available"] else "✗"
        lines.append(f"  {status_icon} {name}: {info['message']}")
        if info.get("fix") and not info["available"]:
            lines.append(f"    Fix: {info['fix']}")

    # Add recommendation
    available = [k for k, v in health.items() if v["available"]]
    if not available:
        lines.append("")
        lines.append("⚠ NO PROVIDERS AVAILABLE - Chat will not work!")
        lines.append("Recommended: Set up Groq (free, fast):")
        lines.append("  1. Get key at: https://console.groq.com")
        lines.append("  2. Run: export GROQ_API_KEY='your-key'")
    elif "groq" not in available:
        lines.append("")
        lines.append("⚠ Groq not available - using slower fallback")
        lines.append("Recommended: Set up Groq for best performance")

    return "\n".join(lines)
