"""
OpenAI TTS integration for high-quality voice synthesis.
Uses OpenAI's TTS API for natural-sounding voice output.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from core import secrets


def speak_openai_tts(text: str, voice: str = "alloy", model: str = "tts-1") -> bool:
    """
    Speak text using OpenAI TTS.
    
    Args:
        text: Text to speak
        voice: Voice name (alloy, echo, fable, onyx, nova, shimmer)
        model: TTS model (tts-1 for speed, tts-1-hd for quality)
    
    Returns:
        True if successful
    """
    # Get OpenRouter key (can route to OpenAI)
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        # Fallback to direct OpenAI key
        api_key = secrets.get_openai_key()
    
    if not api_key:
        print("No OpenAI/OpenRouter API key found")
        return False
    
    try:
        from openai import OpenAI
        
        # Use OpenRouter if that's what we have
        if api_key.startswith("sk-or-"):
            # OpenRouter doesn't support TTS, need actual OpenAI key
            api_key = secrets.get_openai_key()
            if not api_key:
                print("OpenAI TTS requires OpenAI API key (not OpenRouter)")
                return False
        
        client = OpenAI(api_key=api_key)
        
        # Generate speech
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name
        
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
        )
        
        response.stream_to_file(temp_path)
        
        # Log usage for cost tracking
        try:
            from scripts.monitor_tts_costs import log_tts_usage
            log_tts_usage(text, voice, model)
        except Exception as e:
            pass  # Don't fail if logging fails
        
        # Play audio
        subprocess.run(
            ["afplay", temp_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        
        # Cleanup
        Path(temp_path).unlink(missing_ok=True)
        
        return True
        
    except ImportError:
        print("OpenAI package not installed. Install with: pip install openai")
        return False
    except Exception as e:
        print(f"OpenAI TTS failed: {e}")
        return False


def speak_openai_tts_process(text: str, voice: str = "alloy", model: str = "tts-1") -> Optional[subprocess.Popen]:
    """
    Start OpenAI TTS as a subprocess (for barge-in support).
    
    Returns subprocess.Popen or None if failed.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key or api_key.startswith("sk-or-"):
        api_key = secrets.get_openai_key()
    
    if not api_key:
        return None
    
    try:
        from openai import OpenAI
        
        client = OpenAI(api_key=api_key)
        
        # Generate speech
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name
        
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
        )
        
        response.stream_to_file(temp_path)
        
        # Start playback as subprocess
        proc = subprocess.Popen(
            ["afplay", temp_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        
        # Note: temp_path will be cleaned up by caller
        return proc, temp_path
        
    except Exception as e:
        print(f"OpenAI TTS process failed: {e}")
        return None, None


# Voice options for OpenAI TTS
OPENAI_VOICES = {
    "alloy": "Neutral, balanced (default)",
    "echo": "Male, clear",
    "fable": "British accent",
    "onyx": "Deep male voice",
    "nova": "Female, energetic",
    "shimmer": "Female, soft",
}
