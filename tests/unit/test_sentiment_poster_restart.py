from datetime import datetime

import pytest

from bots.twitter.sentiment_poster import SentimentTwitterPoster
from core.context_engine import context


class DummyTwitter:
    def connect(self) -> bool:
        return True

    def disconnect(self) -> None:
        return None


class DummyClaude:
    pass


@pytest.mark.asyncio
async def test_sentiment_poster_skips_initial_when_recent_tweet(monkeypatch):
    previous_last = context.state.get("last_tweet")
    context.state["last_tweet"] = datetime.now().isoformat()
    monkeypatch.setattr(context, "_save_state", lambda: None)

    poster = SentimentTwitterPoster(DummyTwitter(), DummyClaude(), interval_minutes=30)
    calls = {"count": 0}

    async def fake_post():
        calls["count"] += 1

    async def fake_sleep(_seconds):
        poster._running = False

    monkeypatch.setattr(poster, "_post_sentiment_report", fake_post)
    monkeypatch.setattr("bots.twitter.sentiment_poster.asyncio.sleep", fake_sleep)

    try:
        await poster.start()
        assert calls["count"] == 0
    finally:
        if previous_last is None:
            context.state.pop("last_tweet", None)
        else:
            context.state["last_tweet"] = previous_last


@pytest.mark.asyncio
async def test_sentiment_poster_skips_duplicate(monkeypatch):
    class DummyMemory:
        def is_similar_to_recent(self, _text, hours=12, threshold=0.4):
            return True, "previous tweet"

        def record_tweet(self, *args, **kwargs):
            raise AssertionError("Should not record duplicate tweet")

    class DummyTwitterWithPost:
        def __init__(self):
            self.called = False

        async def post_tweet(self, *args, **kwargs):
            self.called = True
            return None

    poster = SentimentTwitterPoster(DummyTwitterWithPost(), DummyClaude(), interval_minutes=30)
    monkeypatch.setattr("bots.twitter.sentiment_poster.get_shared_memory", lambda: DummyMemory())

    tweet_id = await poster._post_tweet("hello world")
    assert tweet_id is None
    assert not poster.twitter.called
