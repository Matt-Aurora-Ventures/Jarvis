"""
LinkedIn Automation Client.
Uses cookie-based session persistence for headless operation.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

from core.automation.browser_cdp import ChromeCDPClient, load_session

logger = logging.getLogger(__name__)

LINKEDIN_SESSION_NAME = 'linkedin'


class LinkedInClient:
    """LinkedIn automation via browser session."""
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._cookies: Dict[str, str] = {}
        self._csrf_token: Optional[str] = None
    
    async def login_via_browser(self, browser: ChromeCDPClient) -> bool:
        """
        Login to LinkedIn via browser automation.
        Requires manual login first time, then saves session.
        """
        await browser.navigate('https://www.linkedin.com/login')
        await asyncio.sleep(2)
        
        # Check if already logged in
        current_url = await browser.execute_script('window.location.href')
        if '/feed' in str(current_url):
            logger.info('Already logged in to LinkedIn')
            await browser.save_session(LINKEDIN_SESSION_NAME)
            return True
        
        logger.info('Please login to LinkedIn manually in the browser...')
        # Wait for manual login (check every 5 seconds)
        for _ in range(60):  # 5 minutes timeout
            await asyncio.sleep(5)
            current_url = await browser.execute_script('window.location.href')
            if '/feed' in str(current_url):
                logger.info('LinkedIn login detected!')
                await browser.save_session(LINKEDIN_SESSION_NAME)
                return True
        
        logger.error('LinkedIn login timeout')
        return False
    
    async def load_session(self) -> bool:
        """Load saved LinkedIn session."""
        session = load_session(LINKEDIN_SESSION_NAME)
        if not session:
            return False
        
        self._cookies = {c['name']: c['value'] for c in session.cookies if 'linkedin' in c.get('domain', '')}
        self._csrf_token = self._cookies.get('JSESSIONID', '').strip('"')
        
        if not self._csrf_token:
            return False
        
        self._session = aiohttp.ClientSession(
            cookies=self._cookies,
            headers={
                'csrf-token': self._csrf_token,
                'x-restli-protocol-version': '2.0.0'
            }
        )
        
        # Verify session
        try:
            async with self._session.get('https://www.linkedin.com/voyager/api/me') as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f'LinkedIn session valid')
                    return True
        except Exception as e:
            logger.error(f'Session verification failed: {e}')
        
        return False
    
    async def close(self):
        if self._session:
            await self._session.close()
    
    async def get_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get LinkedIn profile data."""
        if not self._session:
            return None
        
        url = f'https://www.linkedin.com/voyager/api/identity/profiles/{profile_id}'
        
        try:
            async with self._session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            logger.error(f'Get profile error: {e}')
        
        return None
    
    async def post_update(self, text: str) -> bool:
        """Post a LinkedIn update."""
        if not self._session:
            return False
        
        url = 'https://www.linkedin.com/voyager/api/contentcreation/normShares'
        
        payload = {
            'visibleToConnectionsOnly': False,
            'externalAudienceProviders': [],
            'commentaryV2': {
                'text': text,
                'attributes': []
            },
            'origin': 'MEMBER_SHARE',
            'allowedCommentersScope': 'ALL',
            'content': {},
            'postingContext': {
                'urn': ''
            }
        }
        
        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status in (200, 201):
                    logger.info('LinkedIn post published')
                    return True
                else:
                    logger.error(f'Post failed: {resp.status}')
        except Exception as e:
            logger.error(f'Post error: {e}')
        
        return False
    
    async def send_connection_request(self, profile_urn: str, message: Optional[str] = None) -> bool:
        """Send a connection request."""
        if not self._session:
            return False
        
        url = 'https://www.linkedin.com/voyager/api/growth/normInvitations'
        
        payload = {
            'emberEntityName': 'growth/invitation/norm-invitation',
            'invitee': {
                'com.linkedin.voyager.growth.invitation.InviteeProfile': {
                    'profileId': profile_urn
                }
            },
            'trackingId': ''
        }
        
        if message:
            payload['message'] = message
        
        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status in (200, 201):
                    logger.info(f'Connection request sent to {profile_urn}')
                    return True
        except Exception as e:
            logger.error(f'Connection request error: {e}')
        
        return False


_linkedin: Optional[LinkedInClient] = None

def get_linkedin_client() -> LinkedInClient:
    global _linkedin
    if _linkedin is None:
        _linkedin = LinkedInClient()
    return _linkedin
