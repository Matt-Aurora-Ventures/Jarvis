import contextlib
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import actions, conversation, providers


class FakeProvider:
    def __init__(self, responses: List[str]):
        self._responses = responses
        self.calls = 0

    def __call__(self, prompt: str, max_output_tokens: int = 500, prefer_free: bool = True, diagnostics=None):
        if not self._responses:
            return ""
        idx = min(self.calls, len(self._responses) - 1)
        self.calls += 1
        return self._responses[idx]


class ActionStub:
    def __init__(self):
        self.calls: List[Dict[str, str]] = []

    def __call__(self, action_name: str, **params):
        self.calls.append({"action": action_name, "params": params})
        return True, f"Simulated {action_name}"


@contextlib.contextmanager
def patched(obj, name, value):
    original = getattr(obj, name)
    setattr(obj, name, value)
    try:
        yield
    finally:
        setattr(obj, name, original)


def is_question(text: str) -> bool:
    cleaned = text.strip()
    return "?" in cleaned or cleaned.endswith("?")


def run_scenario(name: str, turns: List[Dict[str, Optional[List[str]]]]) -> Dict[str, int]:
    history: List[Dict[str, str]] = []
    provider_calls = 0
    questions = 0
    action_turn = 0

    for turn_index, turn in enumerate(turns, start=1):
        user_text = turn["user"]
        responses = turn.get("responses") or []
        fake_provider = FakeProvider(responses)
        action_stub = ActionStub()

        with patched(providers, "generate_text", fake_provider), patched(actions, "execute_action", action_stub), patched(conversation, "_record_conversation_turn", lambda *_: None):
            result = conversation.generate_response(user_text, "", session_history=history)

        provider_calls += fake_provider.calls
        if is_question(result):
            questions += 1
        if action_stub.calls and not action_turn:
            action_turn = turn_index

        history.append({"source": "voice_chat_user", "text": user_text})
        history.append({"source": "voice_chat_assistant", "text": result})

    return {
        "provider_calls": provider_calls,
        "questions": questions,
        "action_turn": action_turn,
    }


def main() -> None:
    scenarios = [
        {
            "name": "Direct action: open browser",
            "turns": [
                {"user": "Open browser and go to https://example.com", "responses": []},
            ],
        },
        {
            "name": "Loop breaker after repeat question",
            "turns": [
                {
                    "user": "Build a quick Solana trading bot MVP plan.",
                    "responses": ["Which token should we start with?"],
                },
                {
                    "user": "Just pick one and start.",
                    "responses": [
                        "What's your risk tolerance?",
                        'Proceeding with SOL. [ACTION: create_note(title="Solana MVP", body="MVP plan: data ingest, simple mean reversion, paper test, risk limits.")]',
                    ],
                },
            ],
        },
    ]

    for scenario in scenarios:
        metrics = run_scenario(scenario["name"], scenario["turns"])
        action_turn = metrics["action_turn"] or "none"
        print(f"Scenario: {scenario['name']}")
        print(f"- Provider calls: {metrics['provider_calls']}")
        print(f"- Questions asked: {metrics['questions']}")
        print(f"- Action turn: {action_turn}")
        print("")


if __name__ == "__main__":
    main()
