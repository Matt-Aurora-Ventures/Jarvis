from model_upgrader import ModelUpgrader


def test_model_upgrader_decision_hot_swap_rollback():
    upgrader = ModelUpgrader()
    decision = upgrader.decide(
        {"quality_gain": 0.1, "latency_delta": 0.1, "error_delta": 0.01},
        current="model-a",
        candidate="model-b",
    )
    assert decision.action == "upgrade"

    runtime = {"model": "model-a"}
    upgrader.hot_swap(runtime, "model-b")
    assert runtime["model"] == "model-b"
    upgrader.rollback(runtime)
    assert runtime["model"] == "model-a"
