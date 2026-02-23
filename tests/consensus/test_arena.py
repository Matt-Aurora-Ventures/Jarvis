import pytest

from core.consensus.arena import ConsensusArena


@pytest.mark.asyncio
async def test_arena_run_with_monkeypatched_completion(monkeypatch):
    async def fake_completion(*args, **kwargs):
        class Msg:
            content = "confidence: 0.82 because evidence"

        class Choice:
            message = Msg()

        class Resp:
            choices = [Choice()]

        return Resp()

    class FakeClient:
        async def add(self, *args, **kwargs):
            return True

    monkeypatch.setattr("core.consensus.arena.acompletion", fake_completion)

    class FakeMemoryClient:
        async def add(self, *args, **kwargs):
            return True

    monkeypatch.setattr("core.consensus.arena.get_memory_client", lambda *_args, **_kwargs: FakeMemoryClient())

    arena = ConsensusArena(models=["m1", "m2"])
    out = await arena.run("Analyze tradeoffs and risks")
    assert out["winner"] is not None
    assert len(out["candidates"]) == 2
