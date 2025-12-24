"""
Platform integrations for Jarvis.
Provides connections to Trello, Gmail, Google Calendar, LinkedIn, X/Twitter, and GitHub.
"""

from .trello_integration import TrelloIntegration
from .gmail_integration import GmailIntegration
from .google_calendar_integration import GoogleCalendarIntegration
from .github_integration import GitHubIntegration

__all__ = [
    "TrelloIntegration",
    "GmailIntegration", 
    "GoogleCalendarIntegration",
    "GitHubIntegration",
]
