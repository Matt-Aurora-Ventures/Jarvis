from typing import Optional

from core import config, secrets


def _gemini_client():
    key = secrets.get_gemini_key()
    if not key:
        return None
    try:
        from google import genai
    except Exception:
        return None
    try:
        return genai.Client(api_key=key)
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
    return cfg.get("providers", {}).get("gemini", {}).get("model", "gemini-1.5-flash")


def _openai_model_name(cfg: dict) -> str:
    return cfg.get("providers", {}).get("openai", {}).get("model", "gpt-4o-mini")


def provider_status() -> dict:
    cfg = config.load_config()
    gemini_enabled = cfg.get("providers", {}).get("gemini", {}).get("enabled", True)
    openai_enabled = cfg.get("providers", {}).get("openai", {}).get("enabled", "auto")
    return {
        "gemini_available": bool(_gemini_client()) and bool(gemini_enabled),
        "openai_available": bool(_openai_client())
        and (openai_enabled in (True, "auto")),
    }


def generate_text(prompt: str, max_output_tokens: int = 512) -> Optional[str]:
    cfg = config.load_config()
    status = provider_status()

    if status["gemini_available"]:
        client = _gemini_client()
        if client:
            try:
                from google.genai import types

                response = client.models.generate_content(
                    model=_gemini_model_name(cfg),
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=max_output_tokens
                    ),
                )
                return getattr(response, "text", "") or ""
            except Exception:
                return None

    if status["openai_available"]:
        client = _openai_client()
        if client:
            try:
                response = client.chat.completions.create(
                    model=_openai_model_name(cfg),
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_output_tokens,
                )
                return response.choices[0].message.content or ""
            except Exception:
                return None

    return None
