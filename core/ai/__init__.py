"""
AI Module for Jarvis Trading System

This module provides AI-powered trading analysis including:
- Bull/Bear Debate Architecture for explainable AI trading
- Persona-based analysis with distinct viewpoints
- Synthesis of opposing perspectives into actionable decisions
- Reasoning chain storage for compliance and learning
"""

from .personas import (
    Persona,
    BullPersona,
    BearPersona,
    PersonaFactory,
    PersonaGenerator,
)

from .synthesis import (
    SynthesisResult,
    DebateSynthesizer,
    extract_confidence,
    extract_recommendation,
    build_synthesis_prompt,
)

from .debate_orchestrator import (
    DebateOrchestrator,
    TradeDecision,
)

__all__ = [
    # Personas
    "Persona",
    "BullPersona",
    "BearPersona",
    "PersonaFactory",
    "PersonaGenerator",
    # Synthesis
    "SynthesisResult",
    "DebateSynthesizer",
    "extract_confidence",
    "extract_recommendation",
    "build_synthesis_prompt",
    # Orchestration
    "DebateOrchestrator",
    "TradeDecision",
]
