from core.resilient_provider import ResilientProviderChain


def test_normalize_prompt_result_shapes():
    chain = ResilientProviderChain()

    consensus = chain._normalize_prompt_result("consensus", {"winner": {"provider": "m", "score": 0.8}})
    assert consensus["mode"] == "consensus"
    assert consensus["winner_provider"] == "m"

    nosana = chain._normalize_prompt_result("nosana", {"id": "job-1"})
    assert nosana["mode"] == "job"
    assert nosana["job_id"] == "job-1"

    completion = chain._normalize_prompt_result("groq", "hello")
    assert completion["mode"] == "completion"
    assert completion["result"] == "hello"
