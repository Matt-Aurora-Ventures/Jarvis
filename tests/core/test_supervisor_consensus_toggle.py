from bots.supervisor import should_use_consensus_arena


def test_consensus_toggle_by_query_and_flag():
    assert should_use_consensus_arena("short", enabled=False) is False
    assert should_use_consensus_arena("Please compare risks and tradeoff across options", enabled=True) is True
