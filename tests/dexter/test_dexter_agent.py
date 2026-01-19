"""Tests for Dexter ReAct framework."""

import pytest
import asyncio
from core.dexter.agent import DexterAgent
from core.dexter.config import DexterConfig
from core.dexter.context import ContextManager
from core.dexter.scratchpad import Scratchpad
from core.dexter.tools.meta_router import MetaRouter


@pytest.mark.asyncio
async def test_dexter_agent_init():
    """Test DexterAgent initialization."""
    agent = DexterAgent()
    assert agent.session_id
    assert agent.model == "grok-3"
    assert agent.max_iterations == 15


@pytest.mark.asyncio
async def test_dexter_agent_analyze_token():
    """Test token analysis."""
    agent = DexterAgent()
    decision = await agent.analyze_token("SOL")
    assert decision["symbol"] == "SOL"
    assert decision["action"] in ["BUY", "SELL", "HOLD", "ERROR"]
    assert "confidence" in decision


@pytest.mark.asyncio
async def test_meta_router_liquidations():
    """Test liquidation research."""
    router = MetaRouter()
    result = await router.financial_research("Check liquidation levels for BTC")
    assert "liquidation" in result.lower() or "$" in result


@pytest.mark.asyncio
async def test_meta_router_sentiment():
    """Test sentiment research."""
    router = MetaRouter()
    result = await router.financial_research("Analyze sentiment for SOL")
    assert "sentiment" in result.lower() or "bullish" in result.lower()


def test_scratchpad_logging():
    """Test scratchpad decision logging."""
    scratchpad = Scratchpad("test-session")
    scratchpad.log_start("Analyze SOL", "SOL")
    scratchpad.log_reasoning("Checking market data", 1)
    scratchpad.log_decision("BUY", "SOL", "Bullish setup", 85.0)
    
    entries = scratchpad.get_entries()
    assert len(entries) >= 3
    assert entries[-1]["type"] == "decision"


def test_context_manager():
    """Test context management."""
    ctx = ContextManager("test-session")
    ctx.add_summary("Price: $148, Volume: $2.5B")
    assert ctx.get_token_estimate() > 0


def test_dexter_config():
    """Test configuration."""
    config = DexterConfig(enabled=True, model="grok-3", min_confidence=70.0)
    assert config.enabled
    assert config.model == "grok-3"
    assert config.min_confidence == 70.0


@pytest.mark.asyncio
async def test_dexter_cost_tracking():
    """Test API cost tracking."""
    agent = DexterAgent({"model": "grok-3"})
    initial_cost = agent._cost
    await agent.analyze_token("SOL")
    assert agent._cost >= initial_cost


@pytest.mark.asyncio
async def test_meta_router_returns_string():
    """Test meta-router returns string response."""
    router = MetaRouter()
    result = await router.financial_research("analyze market")
    assert isinstance(result, str)
    assert len(result) > 0


def test_scratchpad_summary():
    """Test scratchpad summary generation."""
    scratchpad = Scratchpad("test-session")
    scratchpad.log_start("Test analysis", "TEST")
    summary = scratchpad.get_summary()
    assert "Market Context" in summary or "Dexter" in summary


@pytest.mark.asyncio
async def test_meta_router_position_analysis():
    """Test position analysis."""
    router = MetaRouter()
    result = await router.financial_research("Check my position risk")
    assert "position" in result.lower() or "risk" in result.lower()


@pytest.mark.asyncio
async def test_dexter_agent_error_handling():
    """Test agent error handling."""
    agent = DexterAgent({"max_iterations": 1})
    decision = await agent.analyze_token("INVALID")
    assert decision is not None
    assert "symbol" in decision


__all__ = []
