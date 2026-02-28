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


@pytest.mark.asyncio
async def test_arena_run_with_gsd_context(monkeypatch):
    async def fake_completion(*args, **kwargs):
        class Msg:
            content = "confidence: 0.75 with spec gates"

        class Choice:
            message = Msg()

        class Resp:
            choices = [Choice()]

        return Resp()

    monkeypatch.setattr("core.consensus.arena.acompletion", fake_completion)

    class FakeMemoryClient:
        async def add(self, *args, **kwargs):
            return True

    monkeypatch.setattr("core.consensus.arena.get_memory_client", lambda *_args, **_kwargs: FakeMemoryClient())

    arena = ConsensusArena(models=["m1"])
    out = await arena.run(
        "Design rollout plan",
        gsd_spec_enabled=True,
        gsd_context_ref="docs/operations/2026-02-28-notebooklm-50q-results.md",
    )
    assert out["gsd_spec_enabled"] is True
    assert "GSD Spec-Driven Evaluation:" in out["effective_prompt"]
