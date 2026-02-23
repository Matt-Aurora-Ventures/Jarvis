"""
Advanced Provider Management System.
Handles quota limits, fallback providers, and rate limiting.
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict, deque

from core import storage_utils, providers

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_PATH = ROOT / "data" / "provider_management"


class ProviderManager:
    """Advanced provider management with quota handling and fallbacks."""
    
    def __init__(self):
        self.storage = storage_utils.get_storage(PROVIDER_PATH)
        
        # Provider status tracking
        self.provider_status = {
            "gemini": {"available": True, "last_error": None, "error_count": 0, "last_used": None},
            "groq": {"available": True, "last_error": None, "error_count": 0, "last_used": None},
            "grok": {"available": True, "last_error": None, "error_count": 0, "last_used": None},
            "ollama": {"available": True, "last_error": None, "error_count": 0, "last_used": None},
            "openai": {"available": True, "last_error": None, "error_count": 0, "last_used": None}
        }

        # Rate limiting
        self.rate_limits = {
            "gemini": {"requests_per_minute": 15, "requests": deque()},
            "groq": {"requests_per_minute": 30, "requests": deque()},
            "grok": {"requests_per_minute": 50, "requests": deque()},
            "openai": {"requests_per_minute": 60, "requests": deque()},
            "ollama": {"requests_per_minute": 100, "requests": deque()}
        }

        # Fallback chain
        self.fallback_chain = ["gemini", "groq", "grok", "openai", "ollama"]
        
        # Load saved status
        self._load_provider_status()
    
    def _load_provider_status(self):
        """Load provider status from storage."""
        saved_status = self.storage.load_txt("provider_status", "dict")
        if saved_status:
            self.provider_status.update(saved_status)
    
    def _save_provider_status(self):
        """Save provider status to storage."""
        self.storage.save_txt("provider_status", self.provider_status)
    
    def _is_rate_limited(self, provider: str) -> bool:
        """Check if provider is rate limited."""
        if provider not in self.rate_limits:
            return False
        
        rate_info = self.rate_limits[provider]
        requests = rate_info["requests"]
        limit = rate_info["requests_per_minute"]
        
        # Clean old requests (older than 1 minute)
        now = time.time()
        while requests and requests[0] < now - 60:
            requests.popleft()
        
        return len(requests) >= limit
    
    def _record_request(self, provider: str):
        """Record a request for rate limiting."""
        if provider in self.rate_limits:
            self.rate_limits[provider]["requests"].append(time.time())
            self.provider_status[provider]["last_used"] = datetime.now().isoformat()
    
    def _mark_provider_error(self, provider: str, error: str):
        """Mark provider as having an error."""
        self.provider_status[provider]["error_count"] += 1
        self.provider_status[provider]["last_error"] = error
        self.provider_status[provider]["last_error_time"] = datetime.now().isoformat()
        
        # Disable provider if too many errors
        if self.provider_status[provider]["error_count"] >= 3:
            self.provider_status[provider]["available"] = False
        
        self._save_provider_status()
    
    def _mark_provider_success(self, provider: str):
        """Mark provider as successful."""
        self.provider_status[provider]["error_count"] = max(0, self.provider_status[provider]["error_count"] - 1)
        self.provider_status[provider]["last_error"] = None
        self.provider_status[provider]["available"] = True
        self._save_provider_status()
    
    def get_best_provider(self) -> Tuple[str, bool]:
        """Get the best available provider."""
        for provider in self.fallback_chain:
            if (self.provider_status[provider]["available"] and 
                not self._is_rate_limited(provider)):
                return provider, True
        
        # If all primary providers are unavailable, try disabled ones
        for provider in self.fallback_chain:
            if not self._is_rate_limited(provider):
                return provider, False
        
        return "gemini", False  # Last resort
    
    def generate_text_with_fallback(self, prompt: str, max_output_tokens: int = 500) -> Dict[str, Any]:
        """Generate text with automatic fallback and error handling."""
        result = {
            "success": False,
            "text": "",
            "provider_used": None,
            "fallback_used": False,
            "error": None,
            "attempt_count": 0
        }
        
        attempts = 0
        max_attempts = len(self.fallback_chain)
        
        while attempts < max_attempts:
            provider, is_primary = self.get_best_provider()
            attempts += 1
            result["attempt_count"] = attempts
            
            if not is_primary and attempts > 1:
                result["fallback_used"] = True
            
            try:
                # Record request for rate limiting
                self._record_request(provider)
                
                # Try to generate text
                if provider == "gemini":
                    text = self._try_gemini(prompt, max_output_tokens)
                elif provider == "groq":
                    text = self._try_groq(prompt, max_output_tokens)
                elif provider == "grok":
                    text = self._try_grok(prompt, max_output_tokens)
                elif provider == "openai":
                    text = self._try_openai(prompt, max_output_tokens)
                elif provider == "ollama":
                    text = self._try_ollama(prompt, max_output_tokens)
                else:
                    continue
                
                if text:
                    result["success"] = True
                    result["text"] = text
                    result["provider_used"] = provider
                    self._mark_provider_success(provider)
                    break
                    
            except Exception as e:
                error_msg = str(e)
                self._mark_provider_error(provider, error_msg)
                result["error"] = error_msg
                
                # If it's a quota error, wait longer before retry
                if "quota" in error_msg.lower() or "429" in error_msg:
                    time.sleep(2)
                else:
                    time.sleep(0.5)
        
        return result
    
    def _try_gemini(self, prompt: str, max_tokens: int) -> str:
        """Try Gemini provider."""
        try:
            # Use existing providers.py functionality
            return providers.generate_text(prompt, max_output_tokens=max_tokens)
        except Exception as e:
            raise Exception(f"Gemini error: {e}")
    
    def _try_groq(self, prompt: str, max_tokens: int) -> str:
        """Try Groq provider."""
        try:
            # Check if Groq is available in providers
            if hasattr(providers, '_groq_client'):
                return providers.generate_text(prompt, max_output_tokens=max_tokens)
            else:
                raise Exception("Groq not available")
        except Exception as e:
            raise Exception(f"Groq error: {e}")

    def _try_grok(self, prompt: str, max_tokens: int) -> str:
        """Try Grok (X.AI) provider."""
        try:
            # Check if Grok is available in providers
            if hasattr(providers, '_grok_client'):
                client = providers._grok_client()
                if client:
                    # Try with the configured model from config
                    from core import config
                    cfg = config.load_config()
                    model = cfg.get("providers", {}).get("grok", {}).get("model", "grok-4-1-fast-non-reasoning")
                    return providers._ask_grok(prompt, model, max_tokens)
                else:
                    raise Exception("Grok client unavailable")
            else:
                raise Exception("Grok not available")
        except Exception as e:
            raise Exception(f"Grok error: {e}")

    def _try_openai(self, prompt: str, max_tokens: int) -> str:
        """Try OpenAI provider."""
        try:
            # Check if OpenAI is available
            if hasattr(providers, '_openai_client'):
                return providers.generate_text(prompt, max_output_tokens=max_tokens)
            else:
                raise Exception("OpenAI not available")
        except Exception as e:
            raise Exception(f"OpenAI error: {e}")
    
    def _try_ollama(self, prompt: str, max_tokens: int) -> str:
        """Try Ollama provider."""
        try:
            # Check if Ollama is available
            if hasattr(providers, '_ollama_client'):
                return providers.generate_text(prompt, max_output_tokens=max_tokens)
            else:
                raise Exception("Ollama not available")
        except Exception as e:
            raise Exception(f"Ollama error: {e}")
    
    def get_provider_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
        stats = {
            "provider_status": self.provider_status.copy(),
            "rate_limits": {},
            "fallback_chain": self.fallback_chain,
            "current_best": self.get_best_provider()[0]
        }
        
        # Add rate limit info
        for provider, info in self.rate_limits.items():
            stats["rate_limits"][provider] = {
                "requests_per_minute": info["requests_per_minute"],
                "current_requests": len(info["requests"])
            }
        
        return stats
    
    def reset_provider_status(self, provider: str = None):
        """Reset provider status."""
        if provider:
            self.provider_status[provider] = {
                "available": True, 
                "last_error": None, 
                "error_count": 0, 
                "last_used": None
            }
        else:
            for p in self.provider_status:
                self.provider_status[p] = {
                    "available": True, 
                    "last_error": None, 
                    "error_count": 0, 
                    "last_used": None
                }
        
        self._save_provider_status()
    
    def disable_provider(self, provider: str, reason: str = "Manual disable"):
        """Manually disable a provider."""
        if provider in self.provider_status:
            self.provider_status[provider]["available"] = False
            self.provider_status[provider]["last_error"] = reason
            self._save_provider_status()
    
    def enable_provider(self, provider: str):
        """Manually enable a provider."""
        if provider in self.provider_status:
            self.provider_status[provider]["available"] = True
            self.provider_status[provider]["error_count"] = 0
            self._save_provider_status()


# Global provider manager instance
_manager: Optional[ProviderManager] = None


def get_provider_manager() -> ProviderManager:
    """Get the global provider manager instance."""
    global _manager
    if not _manager:
        _manager = ProviderManager()
    return _manager


def generate_text_smart(prompt: str, max_output_tokens: int = 500) -> str:
    """Smart text generation with fallbacks."""
    manager = get_provider_manager()
    result = manager.generate_text_with_fallback(prompt, max_output_tokens)
    
    if not result["success"]:
        raise Exception(f"All providers failed. Last error: {result.get('error', 'Unknown')}")
    
    return result["text"]
