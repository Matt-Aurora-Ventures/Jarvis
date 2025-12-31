"""Tests for trading YouTube ingestion helpers (offline)."""

from core import trading_youtube


def test_extract_insights_and_strategies():
    transcript = (
        "We use RSI 30/70 on BTC 1h charts. "
        "Another setup is a moving average crossover, like 50/200. "
        "Always manage risk with stops."
    )
    insights = trading_youtube.extract_insights(transcript, symbols=["BTC"])
    assert "rsi" in insights["indicators"]
    assert "sma" in insights["indicators"]
    assert "1h" in insights["timeframes"]
    assert "BTC" in insights["symbols"]

    jobs = trading_youtube.derive_strategy_hypotheses(insights, symbols=["BTC"])
    assert any(job["strategy"] == "rsi" for job in jobs)
    assert any(job["strategy"] == "sma_cross" for job in jobs)
