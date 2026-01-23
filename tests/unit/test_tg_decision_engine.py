import pytest

from tg_bot.services.tg_decision_engine import TelegramDecisionEngine, Decision


@pytest.mark.asyncio
async def test_should_respond_allows_non_command_message():
    engine = TelegramDecisionEngine()
    result = await engine.should_respond_to_message(
        message_text="jarvis you here",
        user_id=123,
        chat_type="group",
        is_reply_to_bot=False,
    )
    assert result.decision == Decision.EXECUTE
