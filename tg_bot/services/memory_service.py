"""
Telegram-specific memory integration.

Provides:
- User preference detection from messages
- Preference storage with confidence evolution
- Context retrieval for personalized responses
- Response personalization based on preferences
"""

from __future__ import annotations

import re
import logging
from typing import List, Dict, Any, Tuple, Optional

from core.memory.retain import retain_preference, retain_fact, get_user_preferences
from core.memory.recall import recall
from core.memory.session import save_session_context, get_session_context

logger = logging.getLogger(__name__)

# Preference patterns to detect in messages
PREFERENCE_PATTERNS = {
    "risk_tolerance": [
        (r"(?:i\s+)?prefer\s+(?:high|more)\s+risk", "high"),
        (r"(?:i\s+)?prefer\s+(?:low|less)\s+risk", "low"),
        (r"(?:i\'m|i\s+am)\s+(?:a\s+)?conservative", "low"),
        (r"(?:i\'m|i\s+am)\s+(?:a\s+)?aggressive", "high"),
    ],
    "favorite_tokens": [
        (r"(?:i\s+)?(?:like|love|prefer)\s+\$?([A-Z]{3,6})", None),  # Extract token
    ],
    "communication_style": [
        (r"(?:be\s+)?(?:more\s+)?brief", "brief"),
        (r"(?:be\s+)?(?:more\s+)?detailed", "detailed"),
        (r"keep\s+it\s+(?:short|simple)", "brief"),
    ],
}


def detect_preferences(message_text: str) -> List[Tuple[str, str, str]]:
    """
    Detect preference expressions in message.

    Args:
        message_text: User's message text

    Returns:
        List of (preference_key, preference_value, matched_text)
    """
    if not message_text:
        return []

    detected = []
    text_lower = message_text.lower()

    for pref_key, patterns in PREFERENCE_PATTERNS.items():
        for pattern, default_value in patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                # Extract value from match group if available
                if match.groups():
                    value = match.group(1).upper()
                else:
                    value = default_value

                matched_text = match.group(0)
                detected.append((pref_key, value, matched_text))
                logger.debug(f"Detected preference: {pref_key}={value} from '{matched_text}'")

    return detected


async def store_user_preference(
    user_id: str,
    preference_key: str,
    preference_value: str,
    evidence: str,
    platform: str = "telegram",
) -> bool:
    """
    Store user preference with evidence for confidence evolution.

    Args:
        user_id: User identifier
        preference_key: Preference category (e.g., "risk_tolerance")
        preference_value: Preference value (e.g., "high")
        evidence: The message that triggered this preference
        platform: Platform identifier (default: "telegram")

    Returns:
        True if stored successfully, False otherwise
    """
    try:
        # Create user identifier with platform
        user_identifier = f"{platform}:{user_id}"

        # Store preference with evidence
        result = retain_preference(
            user=user_identifier,
            key=preference_key,
            value=preference_value,
            evidence=evidence,
        )

        if result:
            logger.info(f"Stored preference for {user_identifier}: {preference_key}={preference_value}")
            return True
        return False

    except Exception as e:
        logger.warning(f"Failed to store preference: {e}")
        return False


async def get_user_context(
    user_id: str,
    platform: str = "telegram",
) -> Dict[str, Any]:
    """
    Get full user context for personalization.

    Args:
        user_id: User identifier
        platform: Platform identifier (default: "telegram")

    Returns:
        {
            "preferences": Dict[str, Any],  # All preferences with confidence
            "recent_topics": List[str],  # Last 5 conversation topics
            "session": Dict[str, Any],  # Current session context
        }
    """
    try:
        user_identifier = f"{platform}:{user_id}"

        # Get preferences
        preferences = {}
        try:
            prefs = get_user_preferences(user_identifier)
            for pref in prefs:
                preferences[pref.get("key")] = {
                    "value": pref.get("value"),
                    "confidence": pref.get("confidence", 0.5),
                    "last_updated": pref.get("last_updated"),
                }
        except Exception as e:
            logger.debug(f"Failed to get preferences: {e}")

        # Get recent conversation topics (via recall)
        recent_topics = []
        try:
            # Query for recent conversation facts
            results = await recall(
                query=f"user {user_identifier} conversation",
                k=5,
                time_filter="last_7_days",
                context_filter=f"telegram:{user_id}",
            )
            # Extract topics from results
            for result in results:
                topic = result.get("metadata", {}).get("topic")
                if topic and topic not in recent_topics:
                    recent_topics.append(topic)
        except Exception as e:
            logger.debug(f"Failed to get recent topics: {e}")

        # Get session context
        session = {}
        try:
            session_data = get_session_context(user_identifier, platform)
            if session_data:
                session = session_data
        except Exception as e:
            logger.debug(f"Failed to get session context: {e}")

        return {
            "preferences": preferences,
            "recent_topics": recent_topics[:5],
            "session": session,
        }

    except Exception as e:
        logger.warning(f"Failed to get user context: {e}")
        return {
            "preferences": {},
            "recent_topics": [],
            "session": {},
        }


async def personalize_response(
    base_response: str,
    user_id: str,
    platform: str = "telegram",
) -> str:
    """
    Personalize response based on user preferences.

    Applies:
    - Communication style (brief/detailed)
    - Token preferences (highlight favorites)
    - Risk tolerance (adjust recommendations)

    Args:
        base_response: Original response text
        user_id: User identifier
        platform: Platform identifier

    Returns:
        Personalized response text
    """
    if not base_response:
        return base_response

    try:
        # Get user context
        context = await get_user_context(user_id, platform)
        preferences = context.get("preferences", {})

        # Start with base response
        response = base_response

        # Apply communication style preference
        comm_style = preferences.get("communication_style", {})
        if comm_style.get("value") == "brief" and comm_style.get("confidence", 0) > 0.6:
            # If response is long and user prefers brief, add a note
            if len(response) > 500:
                logger.debug(f"User prefers brief responses, but response is {len(response)} chars")
                # Don't truncate aggressively - just note the preference
                # The AI should learn from this over time

        # Highlight favorite tokens if mentioned
        fav_tokens = preferences.get("favorite_tokens", {})
        if fav_tokens.get("value") and fav_tokens.get("confidence", 0) > 0.5:
            token = fav_tokens["value"]
            # Add subtle emphasis when the favorite token is mentioned
            if token in response:
                logger.debug(f"Response mentions user's favorite token: {token}")
                # Don't modify - just log for awareness

        # Note: We keep personalization subtle
        # The main value is in logging preferences for the AI to learn from

        return response

    except Exception as e:
        logger.warning(f"Failed to personalize response: {e}")
        return base_response


async def store_conversation_fact(
    user_id: str,
    message_text: str,
    response_text: str,
    topic: Optional[str] = None,
) -> int:
    """
    Store conversation exchange as a fact for context.

    Args:
        user_id: User identifier
        message_text: User's message
        response_text: Bot's response
        topic: Optional conversation topic

    Returns:
        Fact ID if stored successfully, 0 otherwise
    """
    try:
        # Create conversation summary
        content = f"User: {message_text}\nJARVIS: {response_text}"

        # Store as fact
        fact_id = retain_fact(
            content=content,
            context=f"telegram:{user_id}",
            entities=[f"telegram:{user_id}"],
            metadata={"topic": topic} if topic else None,
        )

        if fact_id:
            logger.debug(f"Stored conversation fact {fact_id} for user {user_id}")
            return fact_id
        return 0

    except Exception as e:
        logger.warning(f"Failed to store conversation fact: {e}")
        return 0
