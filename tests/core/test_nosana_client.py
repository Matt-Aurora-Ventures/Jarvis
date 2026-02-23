import pytest

from nosana_client import NosanaClient


@pytest.mark.asyncio
async def test_nosana_submit_job(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "job-1"}

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("nosana_client.httpx.AsyncClient", lambda *args, **kwargs: FakeAsyncClient())
    client = NosanaClient(base_url="https://example.com")
    out = await client.submit_job({"name": "demo"})
    assert out["id"] == "job-1"
