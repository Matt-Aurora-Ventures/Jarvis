import time
import types

import pytest

from bots.twitter import twitter_client as tc
from core.context_engine import context


class DummyResponse:
    status_code = 401


class DummyTweepyException(Exception):
    def __init__(self):
        super().__init__("unauthorized")
        self.response = DummyResponse()


class DummyLoop:
    async def run_in_executor(self, _executor, func):
        return func()


class DummySearchClient:
    def __init__(self):
        self.called = 0

    def search_recent_tweets(self, **kwargs):
        self.called += 1
        raise DummyTweepyException()


@pytest.mark.asyncio
async def test_search_recent_disables_reads_on_401(monkeypatch):
    monkeypatch.setattr(tc, "HAS_TWEEPY", True)
    monkeypatch.setattr(tc, "TweepyException", DummyTweepyException)
    monkeypatch.setattr(tc.asyncio, "get_event_loop", lambda: DummyLoop())
    monkeypatch.setattr(context, "record_x_read_disable", lambda *_args, **_kwargs: None)

    creds = tc.TwitterCredentials(
        api_key="a",
        api_secret="b",
        access_token="c",
        access_token_secret="d",
    )
    client = tc.TwitterClient(credentials=creds)
    client._username = "jarvis"
    client._tweepy_client = DummySearchClient()
    client._use_oauth2 = False

    results = await client.search_recent("test", max_results=5)
    assert results == []
    assert client._read_disabled_until is not None
    assert client._read_disabled_reason.startswith("search unauthorized")


@pytest.mark.asyncio
async def test_search_recent_skips_when_reads_disabled(monkeypatch):
    creds = tc.TwitterCredentials(
        api_key="a",
        api_secret="b",
        access_token="c",
        access_token_secret="d",
    )
    client = tc.TwitterClient(credentials=creds)
    client._username = "jarvis"

    dummy = DummySearchClient()
    client._tweepy_client = dummy
    client._read_disabled_until = time.time() + 600
    client._read_disabled_reason = "search unauthorized (401)"

    results = await client.search_recent("test", max_results=5)
    assert results == []
    assert dummy.called == 0


@pytest.mark.asyncio
async def test_post_tweet_not_blocked_by_read_disable(monkeypatch):
    class DummyTweepyClient:
        def create_tweet(self, **kwargs):
            return types.SimpleNamespace(data={"id": "123"})

    async def direct_call(func):
        return await func()

    monkeypatch.setattr(tc.asyncio, "get_event_loop", lambda: DummyLoop())
    monkeypatch.setattr(tc, "_get_telegram_sync", lambda: None)

    creds = tc.TwitterCredentials(
        api_key="a",
        api_secret="b",
        access_token="c",
        access_token_secret="d",
    )
    client = tc.TwitterClient(credentials=creds)
    client._username = "jarvis"
    client._tweepy_client = DummyTweepyClient()
    client._use_oauth2 = False
    client._read_disabled_until = time.time() + 600

    monkeypatch.setattr(client._circuit_breaker, "call", direct_call)

    result = await client.post_tweet("hello")
    assert result.success is True
    assert result.tweet_id == "123"
