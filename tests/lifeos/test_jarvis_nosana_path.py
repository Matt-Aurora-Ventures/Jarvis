import pytest

from lifeos.jarvis import Jarvis


@pytest.mark.asyncio
async def test_jarvis_nosana_for_complex_path(monkeypatch):
    jarvis = Jarvis()

    class FakeHookClient:
        async def pre_recall(self, query, context=None):
            return {"query": query, "memory_hints": []}

        async def post_response(self, query, response, context=None):
            return True

    jarvis._supermemory = FakeHookClient()

    class FakeChain:
        async def execute_prompt(self, **kwargs):
            return {
                "provider": "nosana",
                "job_id": "job-42",
                "result": {"id": "job-42"},
            }

    monkeypatch.setattr("lifeos.jarvis.get_provider_chain", lambda: FakeChain())

    await jarvis.start()
    jarvis._config.set("llm.consensus_for_complex", True)
    out = await jarvis.chat("Please compare risks and analyze tradeoff of three strategies")
    assert "Nosana job submitted: job-42" == out
    await jarvis.stop()
