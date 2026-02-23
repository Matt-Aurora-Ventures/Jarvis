import pytest

from lifeos.jarvis import Jarvis


@pytest.mark.asyncio
async def test_chat_invokes_supermemory_hooks(monkeypatch):
    jarvis = Jarvis()

    class FakeHookClient:
        async def pre_recall(self, query, context=None):
            return {"query": query, "context": context or {}, "memory_hints": []}

        async def post_response(self, query, response, context=None):
            return True

    jarvis._supermemory = FakeHookClient()

    class FakeResponse:
        content = "hello"
        model = "fake-model"

    class FakeLLM:
        async def chat(self, *args, **kwargs):
            return FakeResponse()

    await jarvis.start()
    jarvis._llm = FakeLLM()
    out = await jarvis.chat("test message", context={"context_type": "general"})
    assert out
    await jarvis.stop()
