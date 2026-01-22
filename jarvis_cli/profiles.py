"""Service profile definitions for jarvis CLI."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Profile:
    name: str
    description: str
    required_env: List[str] = field(default_factory=list)
    optional_env: List[str] = field(default_factory=list)

    def missing_required(self, env: Dict[str, str]) -> List[str]:
        return [key for key in self.required_env if not env.get(key)]


def get_profiles() -> Dict[str, Profile]:
    return {
        "voice": Profile(
            name="voice",
            description="Local speaking/chat assistant with graceful fallbacks.",
        ),
        "telegram": Profile(
            name="telegram",
            description="Telegram bot (requires TELEGRAM_BOT_TOKEN).",
            required_env=["TELEGRAM_BOT_TOKEN"],
        ),
        "twitter": Profile(
            name="twitter",
            description="Autonomous X/Twitter bot (requires API keys).",
            required_env=[
                "X_API_KEY",
                "X_API_SECRET",
                "X_ACCESS_TOKEN",
                "X_ACCESS_TOKEN_SECRET",
            ],
            optional_env=["X_BEARER_TOKEN"],
        ),
        "all": Profile(
            name="all",
            description="Start all available profiles with graceful degradation.",
        ),
    }
