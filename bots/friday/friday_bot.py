"""
Friday - KR8TIV AI Email Assistant

Named after Tony Stark's AI assistant, Friday helps process emails and provide
intelligent, professional responses aligned with KR8TIV AI's brand.

Features:
- Email inbox monitoring (IMAP)
- AI-powered response generation (Grok)
- Brand-aligned communication style
- Auto-categorization (urgent, info, spam, etc.)
- Smart reply suggestions
- Integration with calendar/tasks (future)

Origin: ClawdMatt GSD-TODO #1 (Jan 29, 2026)
Voice note: "get a email AI called Friday, should match KR8TIV AI branding"

References:
- docs/KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md (brand voice)
- Iron Man's FRIDAY: https://marvelcinematicuniverse.fandom.com/wiki/F.R.I.D.A.Y.

"""

import asyncio
import logging
import os
import json
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Literal
from dataclasses import dataclass, asdict
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import aiohttp
from aiohttp import ClientTimeout

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Represents an email message."""
    message_id: str
    from_addr: str
    to_addr: str
    subject: str
    body: str
    date: str
    category: Optional[str] = None
    priority: Optional[str] = None  # urgent, normal, low
    suggested_response: Optional[str] = None


@dataclass
class EmailResponse:
    """Suggested response to an email."""
    original_message_id: str
    response_text: str
    confidence: float
    reasoning: str
    should_send_auto: bool  # True if safe to auto-send


class FridayEmailAI:
    """
    Friday - KR8TIV AI Email Assistant

    Helps process incoming emails and generate professional responses
    aligned with KR8TIV AI's brand voice.
    """

    # Email categories
    CATEGORIES = [
        "business_inquiry",    # New business opportunities
        "technical_support",   # Support requests
        "partnership",         # Partnership proposals
        "investor",           # Investment inquiries
        "community",          # Community questions
        "spam",               # Spam/marketing
        "personal",           # Personal messages
        "urgent",             # Requires immediate attention
        "info",               # FYI only, no response needed
    ]

    # Priority levels
    URGENT_KEYWORDS = [
        "urgent", "asap", "immediately", "critical", "emergency",
        "time-sensitive", "deadline", "today", "now"
    ]

    def __init__(
        self,
        xai_api_key: str,
        user_email: str,
        brand_guide_path: Optional[str] = None,
        auto_respond: bool = False,  # If True, auto-send non-urgent responses
    ):
        self.xai_api_key = xai_api_key
        self.user_email = user_email
        self.brand_guide_path = brand_guide_path or "docs/KR8TIV_AI_MARKETING_GUIDE_JAN_31_2026.md"
        self.auto_respond = auto_respond
        self._session: Optional[aiohttp.ClientSession] = None
        self._brand_guide_content: Optional[str] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    async def start(self):
        """Initialize Friday."""
        self._session = aiohttp.ClientSession(
            timeout=ClientTimeout(total=60)
        )
        await self._load_brand_guide()
        logger.info("Friday Email AI started")

    async def stop(self):
        """Clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
        logger.info("Friday Email AI stopped")

    async def _load_brand_guide(self):
        """Load brand guidelines for communication style."""
        try:
            guide_path = Path(self.brand_guide_path)
            if guide_path.exists():
                self._brand_guide_content = guide_path.read_text(encoding='utf-8')
                logger.info(f"Loaded brand guide ({len(self._brand_guide_content)} chars)")
            else:
                logger.warning(f"Brand guide not found at {guide_path}")
                self._brand_guide_content = ""
        except Exception as e:
            logger.error(f"Error loading brand guide: {e}")
            self._brand_guide_content = ""

    def _categorize_email(self, email: EmailMessage) -> Tuple[str, str]:
        """
        Quickly categorize email and determine priority.
        Returns (category, priority)
        """
        subject_lower = email.subject.lower()
        body_lower = email.body.lower()
        combined = f"{subject_lower} {body_lower}"

        # Check for urgent
        priority = "normal"
        for keyword in self.URGENT_KEYWORDS:
            if keyword in combined:
                priority = "urgent"
                break

        # Quick category detection
        if any(word in combined for word in ["invest", "fund", "vc", "capital"]):
            category = "investor"
        elif any(word in combined for word in ["partner", "collaboration", "integrate"]):
            category = "partnership"
        elif any(word in combined for word in ["bug", "error", "issue", "help", "support"]):
            category = "technical_support"
        elif any(word in combined for word in ["opportunity", "proposal", "business"]):
            category = "business_inquiry"
        elif any(word in combined for word in ["community", "question", "how to"]):
            category = "community"
        elif re.search(r'unsubscribe|click here|free|offer|limited time', combined):
            category = "spam"
        else:
            category = "info"

        return category, priority

    async def _generate_response_with_grok(
        self,
        email: EmailMessage,
        category: str,
        priority: str
    ) -> Dict:
        """Use Grok AI to generate a professional response."""

        # Extract brand voice guidance
        brand_voice = ""
        if self._brand_guide_content:
            # Get voice & tone section (first ~2000 chars has key guidelines)
            brand_voice = self._brand_guide_content[:2000]

        prompt = f"""You are Friday, the email AI assistant for KR8TIV AI. You help draft professional, authentic email responses that match the brand voice.

BRAND VOICE GUIDELINES:
{brand_voice}

KEY PRINCIPLES:
- Professional but authentic
- Technical credibility + accessibility
- Honest and transparent
- Action-oriented (propose next steps)
- No overpromising or hype

EMAIL CONTEXT:
From: {email.from_addr}
Subject: {email.subject}
Category: {category}
Priority: {priority}

EMAIL BODY:
{email.body}

TASK: Generate a professional email response following these guidelines:

1. For BUSINESS_INQUIRY: Express interest, ask clarifying questions, propose next steps
2. For TECHNICAL_SUPPORT: Acknowledge issue, provide guidance or escalate
3. For PARTNERSHIP: Show openness, highlight synergies, suggest call/meeting
4. For INVESTOR: Professional interest, share traction, suggest follow-up
5. For COMMUNITY: Helpful, concise answer or point to resources
6. For SPAM: DO NOT RESPOND (mark as spam)
7. For INFO: Brief acknowledgment if appropriate, otherwise no response needed

RESPONSE FORMAT:
{{
  "should_respond": true|false,
  "response_text": "email body here" or null,
  "reasoning": "why this response / why no response",
  "confidence": 0.0-1.0,
  "suggested_next_steps": ["action1", "action2"],
  "safe_to_auto_send": true|false
}}

Respond ONLY with valid JSON.
"""

        try:
            async with self._session.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "grok-beta",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are Friday, KR8TIV AI's email assistant. Respond only with valid JSON."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.5,  # Balanced creativity + consistency
                    "max_tokens": 800
                }
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Grok API error: {resp.status} - {error_text}")
                    return {
                        "should_respond": False,
                        "response_text": None,
                        "reasoning": f"AI error: {resp.status}",
                        "confidence": 0.0,
                        "suggested_next_steps": [],
                        "safe_to_auto_send": False
                    }

                data = await resp.json()
                content = data["choices"][0]["message"]["content"]

                # Extract JSON
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    return result
                else:
                    logger.error(f"Could not parse Grok response: {content}")
                    return {
                        "should_respond": False,
                        "response_text": None,
                        "reasoning": "Parse error",
                        "confidence": 0.0,
                        "suggested_next_steps": [],
                        "safe_to_auto_send": False
                    }

        except Exception as e:
            logger.error(f"Error calling Grok API: {e}")
            return {
                "should_respond": False,
                "response_text": None,
                "reasoning": f"Exception: {str(e)}",
                "confidence": 0.0,
                "suggested_next_steps": [],
                "safe_to_auto_send": False
            }

    async def process_email(
        self,
        email: EmailMessage
    ) -> EmailResponse:
        """
        Process an email and generate a suggested response.

        Args:
            email: The email to process

        Returns:
            EmailResponse with suggested reply (or None if no response needed)
        """
        logger.info(f"Friday processing email: {email.subject} from {email.from_addr}")

        # Categorize
        category, priority = self._categorize_email(email)
        email.category = category
        email.priority = priority

        logger.info(f"Categorized as: {category} (priority: {priority})")

        # Generate response with AI
        ai_result = await self._generate_response_with_grok(email, category, priority)

        response = EmailResponse(
            original_message_id=email.message_id,
            response_text=ai_result.get("response_text"),
            confidence=ai_result.get("confidence", 0.0),
            reasoning=ai_result.get("reasoning", ""),
            should_send_auto=ai_result.get("safe_to_auto_send", False) and self.auto_respond
        )

        logger.info(f"Friday response: {response.confidence:.2f} confidence, auto-send: {response.should_send_auto}")

        return response

    async def get_inbox_summary(self, emails: List[EmailMessage]) -> Dict:
        """Generate a summary of inbox emails."""
        categorized = {}
        urgent_count = 0

        for email in emails:
            category, priority = self._categorize_email(email)
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(email)

            if priority == "urgent":
                urgent_count += 1

        summary = {
            "total": len(emails),
            "urgent": urgent_count,
            "by_category": {
                cat: len(emails_list)
                for cat, emails_list in categorized.items()
            },
            "needs_response": len(emails) - categorized.get("spam", []) - categorized.get("info", [])
        }

        return summary


# Future: Email fetching (IMAP integration)
class FridayEmailFetcher:
    """
    IMAP email fetcher for Friday.
    TODO: Implement IMAP connection and email parsing.
    """
    def __init__(self, imap_server: str, email: str, password: str):
        self.imap_server = imap_server
        self.email = email
        self.password = password

    async def fetch_unread(self) -> List[EmailMessage]:
        """Fetch unread emails from inbox."""
        # TODO: Implement IMAP connection
        logger.warning("Email fetching not yet implemented")
        return []


async def main():
    """Test Friday with sample emails."""
    xai_api_key = os.getenv("XAI_API_KEY", "")
    if not xai_api_key:
        print("Error: XAI_API_KEY not set")
        return

    async with FridayEmailAI(
        xai_api_key=xai_api_key,
        user_email="matt@kr8tiv.ai"
    ) as friday:
        # Test emails
        test_emails = [
            EmailMessage(
                message_id="1",
                from_addr="investor@vc.com",
                to_addr="matt@kr8tiv.ai",
                subject="Investment Opportunity in KR8TIV AI",
                body="Hi Matt, I'm interested in learning more about KR8TIV AI and potential investment. Can we schedule a call?",
                date=datetime.now(timezone.utc).isoformat()
            ),
            EmailMessage(
                message_id="2",
                from_addr="spam@marketing.com",
                to_addr="matt@kr8tiv.ai",
                subject="Limited Time Offer: 50% Off!",
                body="Click here to claim your amazing offer! Unsubscribe here.",
                date=datetime.now(timezone.utc).isoformat()
            ),
            EmailMessage(
                message_id="3",
                from_addr="community@bags.fm",
                to_addr="matt@kr8tiv.ai",
                subject="URGENT: Critical Bug in Trading Bot",
                body="Hey Matt, we found a critical issue with the trading bot. It's crashing on startup. Please help ASAP!",
                date=datetime.now(timezone.utc).isoformat()
            ),
        ]

        for email in test_emails:
            print(f"\n{'='*80}")
            print(f"From: {email.from_addr}")
            print(f"Subject: {email.subject}")
            print("-" * 80)

            response = await friday.process_email(email)

            print(f"Category: {email.category}")
            print(f"Priority: {email.priority}")
            print(f"Should Respond: {response.response_text is not None}")
            if response.response_text:
                print(f"\nSuggested Response:\n{response.response_text}")
            print(f"\nReasoning: {response.reasoning}")
            print(f"Confidence: {response.confidence:.2f}")
            print(f"Auto-send: {response.should_send_auto}")


if __name__ == "__main__":
    asyncio.run(main())
