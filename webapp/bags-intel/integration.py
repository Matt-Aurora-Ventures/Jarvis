"""
Integration module to connect bags_intel service with the webapp API
Call this from the intel_service to push events to the webapp
"""

import sys
from pathlib import Path
import requests
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from bots.bags_intel.models import GraduationEvent
except ImportError:
    print("Warning: Could not import bags_intel models")
    GraduationEvent = None


class WebappIntegration:
    """Handles communication between bags_intel service and webapp"""

    def __init__(self, api_url: str = "http://localhost:5000"):
        self.api_url = api_url.rstrip('/')
        self.enabled = True

    def check_health(self) -> bool:
        """Check if webapp API is available"""
        try:
            response = requests.get(f"{self.api_url}/api/health", timeout=2)
            return response.status_code == 200
        except Exception:
            return False

    def notify_graduation(self, event: GraduationEvent) -> bool:
        """Send graduation event to webapp"""
        if not self.enabled:
            return False

        try:
            event_dict = event.to_dict() if hasattr(event, 'to_dict') else event
            response = requests.post(
                f"{self.api_url}/api/bags-intel/webhook",
                json=event_dict,
                timeout=5
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Failed to notify webapp: {e}")
            return False

    def get_recent_events(self, limit: int = 20) -> list:
        """Fetch recent events from webapp API"""
        try:
            response = requests.get(
                f"{self.api_url}/api/bags-intel/graduations",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            events = data.get('events', [])
            return events[:limit]
        except Exception as e:
            print(f"Failed to fetch events: {e}")
            return []


# Global instance for easy import
webapp_integration = WebappIntegration()


# Convenience function for direct use
def notify_webapp(event: GraduationEvent) -> bool:
    """Convenience function to notify webapp of a new graduation"""
    return webapp_integration.notify_graduation(event)


if __name__ == "__main__":
    # Test the integration
    print("Testing webapp integration...")

    integration = WebappIntegration()

    if integration.check_health():
        print("✅ Webapp API is healthy")

        events = integration.get_recent_events(limit=5)
        print(f"✅ Fetched {len(events)} recent events")

        if events:
            print("\nRecent graduations:")
            for event in events[:3]:
                token = event.get('token', {})
                scores = event.get('scores', {})
                print(f"  - {token.get('symbol')}: {scores.get('overall')}/100 ({scores.get('quality')})")
    else:
        print("❌ Webapp API is not available")
        print("   Make sure the server is running: python api.py")
