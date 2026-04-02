"""
Voice Plugin for LifeOS.

Integrates voice/TTS capabilities with the persona system:
- Persona-aware voice selection
- Speaking style adaptation
- Text-to-speech synthesis
- Speech-to-text transcription
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from lifeos.plugins.base import Plugin
from lifeos.pae.base import EvaluationResult

logger = logging.getLogger(__name__)


@dataclass
class VoiceConfig:
    """Voice configuration for a persona."""
    voice_name: str = ""
    speech_rate: int = 180
    pitch: float = 1.0
    tts_engine: str = "piper"
    language: str = "en"


# Default persona-to-voice mappings
DEFAULT_VOICE_MAPPINGS = {
    "jarvis": VoiceConfig(
        voice_name="Reed",
        speech_rate=180,
        tts_engine="piper",
    ),
    "casual": VoiceConfig(
        voice_name="Samantha",
        speech_rate=200,
        tts_engine="say",
    ),
    "buddy": VoiceConfig(
        voice_name="Samantha",
        speech_rate=200,
        tts_engine="say",
    ),
    "analyst": VoiceConfig(
        voice_name="Daniel",
        speech_rate=160,
        tts_engine="piper",
    ),
    "teacher": VoiceConfig(
        voice_name="Ava",
        speech_rate=170,
        tts_engine="say",
    ),
    "coder": VoiceConfig(
        voice_name="Alex",
        speech_rate=190,
        tts_engine="piper",
    ),
}


class SpeakAction:
    """Action to speak text with persona-aware voice."""

    name = "voice.speak"
    description = "Speak text using TTS with persona-aware voice"
    requires_confirmation = False

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._voice_module = None
        self._persona_manager = None

    def set_voice_module(self, module) -> None:
        """Set the voice module."""
        self._voice_module = module

    def set_persona_manager(self, manager) -> None:
        """Set the persona manager."""
        self._persona_manager = manager

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute speak action."""
        text = params.get("text")
        persona = params.get("persona")

        if not text:
            raise ValueError("text is required")

        if not self._voice_module:
            return {
                "success": False,
                "error": "Voice module not available",
            }

        # Get voice config for persona
        voice_config = self._get_voice_config(persona)

        # Speak the text
        try:
            success = self._voice_module.speak_text(text)
            return {
                "success": success,
                "text_length": len(text),
                "voice": voice_config.voice_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _get_voice_config(self, persona_name: Optional[str]) -> VoiceConfig:
        """Get voice config for persona."""
        if persona_name:
            name_lower = persona_name.lower()
            if name_lower in DEFAULT_VOICE_MAPPINGS:
                return DEFAULT_VOICE_MAPPINGS[name_lower]

        # Get from custom mappings in config
        mappings = self._config.get("persona_voice_mapping", {})
        if persona_name and persona_name.lower() in mappings:
            mapping = mappings[persona_name.lower()]
            return VoiceConfig(
                voice_name=mapping.get("voice", ""),
                speech_rate=mapping.get("rate", 180),
            )

        return VoiceConfig()


class TranscribeAction:
    """Action to transcribe speech to text."""

    name = "voice.transcribe"
    description = "Transcribe audio input to text"
    requires_confirmation = False

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._voice_module = None

    def set_voice_module(self, module) -> None:
        """Set the voice module."""
        self._voice_module = module

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute transcription."""
        timeout = params.get("timeout", 6)
        phrase_limit = params.get("phrase_limit", 6)

        if not self._voice_module:
            return {
                "success": False,
                "error": "Voice module not available",
            }

        try:
            # Use internal transcription function
            text = self._voice_module._transcribe_once(
                timeout=timeout,
                phrase_time_limit=phrase_limit
            )
            return {
                "success": bool(text),
                "text": text,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class VoiceStatusProvider:
    """Provider for voice system status."""

    name = "voice.status"
    description = "Get voice system status"

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._voice_module = None

    def set_voice_module(self, module) -> None:
        """Set the voice module."""
        self._voice_module = module

    async def provide(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Provide voice status."""
        if not self._voice_module:
            return {
                "available": False,
                "error": "Voice module not available",
            }

        try:
            runtime_status = self._voice_module.get_voice_runtime_status()
            return {
                "available": True,
                "speaking": runtime_status.get("speaking", False),
                "last_spoken_at": runtime_status.get("last_spoken_at", 0),
                "last_spoken_text": runtime_status.get("last_spoken_text", ""),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e),
            }


class PersonaVoiceProvider:
    """Provider for persona voice mappings."""

    name = "voice.persona_mapping"
    description = "Get voice configuration for personas"

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config

    async def provide(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Provide persona voice mappings."""
        persona = query.get("persona")

        if persona:
            name_lower = persona.lower()
            if name_lower in DEFAULT_VOICE_MAPPINGS:
                vc = DEFAULT_VOICE_MAPPINGS[name_lower]
                return {
                    "persona": persona,
                    "voice_name": vc.voice_name,
                    "speech_rate": vc.speech_rate,
                    "tts_engine": vc.tts_engine,
                    "language": vc.language,
                }

        # Return all mappings
        mappings = {}
        for name, vc in DEFAULT_VOICE_MAPPINGS.items():
            mappings[name] = {
                "voice_name": vc.voice_name,
                "speech_rate": vc.speech_rate,
                "tts_engine": vc.tts_engine,
            }

        return {
            "mappings": mappings,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class VoiceHealthEvaluator:
    """Evaluator for voice system health."""

    name = "voice.health"
    description = "Evaluate voice system health"

    def __init__(self, plugin_id: str, config: Dict[str, Any]):
        self._plugin_id = plugin_id
        self._config = config
        self._voice_module = None

    def set_voice_module(self, module) -> None:
        """Set the voice module."""
        self._voice_module = module

    async def evaluate(self, context: Dict[str, Any]) -> EvaluationResult:
        """Evaluate voice health."""
        if not self._voice_module:
            return EvaluationResult(
                decision=False,
                confidence=0.0,
                reasoning="Voice module not available",
                metadata={},
            )

        try:
            if hasattr(self._voice_module, 'check_voice_health'):
                health = self._voice_module.check_voice_health()

                mic_ok = health.get("microphone", {}).get("ok", False)
                stt_ok = health.get("stt", {}).get("any_working", False)
                tts_ok = health.get("tts", {}).get("any_working", False)

                all_ok = mic_ok and stt_ok and tts_ok
                issues = []

                if not mic_ok:
                    issues.append("microphone")
                if not stt_ok:
                    issues.append("speech-to-text")
                if not tts_ok:
                    issues.append("text-to-speech")

                confidence = sum([mic_ok, stt_ok, tts_ok]) / 3.0

                return EvaluationResult(
                    decision=all_ok,
                    confidence=confidence,
                    reasoning=f"Voice pipeline {'healthy' if all_ok else 'has issues'}: {', '.join(issues) if issues else 'all systems operational'}",
                    metadata=health,
                )
            else:
                return EvaluationResult(
                    decision=True,
                    confidence=0.5,
                    reasoning="Voice module available but health check not implemented",
                    metadata={},
                )
        except Exception as e:
            return EvaluationResult(
                decision=False,
                confidence=0.0,
                reasoning=f"Health check failed: {str(e)}",
                metadata={},
            )


class VoicePlugin(Plugin):
    """
    Voice integration plugin.

    Provides:
    - Persona-aware TTS
    - Speech transcription
    - Voice health monitoring
    - Event-driven speech
    """

    def __init__(self, context, manifest):
        super().__init__(context, manifest)
        self._voice_module = None
        self._persona_manager = None
        self._actions: List[Any] = []
        self._providers: List[Any] = []
        self._evaluators: List[Any] = []

    async def on_load(self) -> None:
        """Initialize the plugin."""
        logger.info("Loading Voice plugin")

        # Try to import the voice module
        try:
            from core import voice
            self._voice_module = voice
            logger.info("Voice module loaded")
        except ImportError as e:
            logger.warning(f"Voice module not available: {e}")
            self._voice_module = None

        # Try to get persona manager from jarvis
        if self._context and "jarvis" in self._context.services:
            jarvis = self._context.services["jarvis"]
            if hasattr(jarvis, "persona_manager"):
                self._persona_manager = jarvis.persona_manager

        # Get plugin config
        config = self._context.config if self._context else {}

        # Create PAE components
        speak_action = SpeakAction(self._manifest.name, config)
        speak_action.set_voice_module(self._voice_module)
        speak_action.set_persona_manager(self._persona_manager)

        transcribe_action = TranscribeAction(self._manifest.name, config)
        transcribe_action.set_voice_module(self._voice_module)

        self._actions = [speak_action, transcribe_action]

        status_provider = VoiceStatusProvider(self._manifest.name, config)
        status_provider.set_voice_module(self._voice_module)

        persona_provider = PersonaVoiceProvider(self._manifest.name, config)

        self._providers = [status_provider, persona_provider]

        health_evaluator = VoiceHealthEvaluator(self._manifest.name, config)
        health_evaluator.set_voice_module(self._voice_module)

        self._evaluators = [health_evaluator]

        # Register with PAE if available
        if self._context and "jarvis" in self._context.services:
            jarvis = self._context.services["jarvis"]
            if hasattr(jarvis, "pae"):
                for action in self._actions:
                    jarvis.pae.register_action(action)
                for provider in self._providers:
                    jarvis.pae.register_provider(provider)
                for evaluator in self._evaluators:
                    jarvis.pae.register_evaluator(evaluator)
                logger.info("Registered Voice PAE components")

    async def on_enable(self) -> None:
        """Enable the plugin."""
        logger.info("Enabling Voice plugin")

        # Subscribe to speak events
        if self._context and "event_bus" in self._context.services:
            event_bus = self._context.services["event_bus"]

            @event_bus.on("voice.speak_request")
            async def handle_speak_request(event):
                text = event.data.get("text", "")
                persona = event.data.get("persona")
                if text and self._voice_module:
                    self._voice_module.speak_text(text)
                    await event_bus.emit("voice.spoke", {
                        "text": text,
                        "persona": persona,
                    })

            @event_bus.on("persona.changed")
            async def handle_persona_change(event):
                # Could update voice settings based on new persona
                new_persona = event.data.get("name", "")
                logger.info(f"Persona changed to: {new_persona}")

            await event_bus.emit("voice.enabled", {
                "module_available": self._voice_module is not None,
            })

    async def on_disable(self) -> None:
        """Disable the plugin."""
        logger.info("Disabling Voice plugin")

        # Stop any active speech
        if self._voice_module and hasattr(self._voice_module, '_stop_active_speech'):
            self._voice_module._stop_active_speech()

        if self._context and "event_bus" in self._context.services:
            await self._context.services["event_bus"].emit("voice.disabled")

    async def on_unload(self) -> None:
        """Clean up plugin resources."""
        logger.info("Unloading Voice plugin")
        self._voice_module = None
        self._persona_manager = None
        self._actions.clear()
        self._providers.clear()
        self._evaluators.clear()

    # Public API methods

    def speak(self, text: str, persona: Optional[str] = None) -> bool:
        """Speak text with optional persona voice."""
        if not self._voice_module:
            return False

        # Get voice config for persona and configure
        voice_config = self._get_voice_config(persona)

        # For now, just speak with default voice
        # In full implementation, would configure voice_cfg before speaking
        return self._voice_module.speak_text(text)

    def transcribe(self, timeout: int = 6, phrase_limit: int = 6) -> str:
        """Transcribe audio to text."""
        if not self._voice_module:
            return ""

        return self._voice_module._transcribe_once(
            timeout=timeout,
            phrase_time_limit=phrase_limit
        )

    def get_status(self) -> Dict[str, Any]:
        """Get voice system status."""
        if not self._voice_module:
            return {"available": False}

        return self._voice_module.get_voice_runtime_status()

    def get_health(self) -> Dict[str, Any]:
        """Get voice system health."""
        if not self._voice_module:
            return {"available": False}

        if hasattr(self._voice_module, 'check_voice_health'):
            return self._voice_module.check_voice_health()

        return {"available": True}

    def get_voice_for_persona(self, persona_name: str) -> Optional[VoiceConfig]:
        """Get voice configuration for a persona."""
        return self._get_voice_config(persona_name)

    def _get_voice_config(self, persona_name: Optional[str]) -> VoiceConfig:
        """Get voice config for persona."""
        if persona_name:
            name_lower = persona_name.lower()
            if name_lower in DEFAULT_VOICE_MAPPINGS:
                return DEFAULT_VOICE_MAPPINGS[name_lower]

        return VoiceConfig()

    def is_available(self) -> bool:
        """Check if voice module is available."""
        return self._voice_module is not None
