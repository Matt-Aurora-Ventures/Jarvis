from core.resilient_provider import ResilientProviderChain


def test_default_providers_include_consensus_and_nosana():
    chain = ResilientProviderChain()
    names = [p.name for p in chain.providers]
    assert "consensus" in names
    assert "nosana" in names
