import pytest

from bots.supervisor import run_complex_query_arena


@pytest.mark.asyncio
async def test_run_complex_query_arena(monkeypatch):
    class FakeArena:
        def __init__(self, models=None):
            self.models = models

        async def run(self, query):
            return {"prompt": query, "winner": {"provider": "m1", "score": 0.8}}

    monkeypatch.setattr("bots.supervisor.ConsensusArena", FakeArena)
    out = await run_complex_query_arena("analyze risks and tradeoff")
    assert out["winner"]["provider"] == "m1"
