"""
Automation Orchestrator - Central controller for all automation.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import all automation modules
from core.automation.credential_manager import get_credential_manager
from core.automation.browser_cdp import ChromeCDPClient, launch_chrome_with_debugging, load_session
from core.automation.google_oauth import get_google_manager
from core.automation.x_multi_account import get_x_manager
from core.automation.linkedin_client import get_linkedin_client
from core.automation.gui_automation import get_gui_automation
from core.automation.wake_on_lan import get_wol_manager
from core.automation.task_scheduler import get_task_scheduler


class AutomationOrchestrator:
    """
    Central orchestrator for all computer automation.
    Coordinates browser, credentials, OAuth, and system automation.
    """
    
    def __init__(self):
        self._browser: Optional[ChromeCDPClient] = None
        self._initialized = False
    
    async def initialize(self, debug_port: int = 9222) -> bool:
        """Initialize all automation components."""
        logger.info('Initializing automation orchestrator...')
        
        # Initialize browser connection
        self._browser = ChromeCDPClient()
        browser_connected = await self._browser.connect(debug_port)
        
        if not browser_connected:
            logger.warning('Browser not connected. Launching Chrome...')
            if await launch_chrome_with_debugging(debug_port):
                await asyncio.sleep(3)
                browser_connected = await self._browser.connect(debug_port)
        
        if browser_connected:
            logger.info('Browser connected')
        
        self._initialized = True
        logger.info('Automation orchestrator initialized')
        return True
    
    async def shutdown(self):
        """Shutdown all automation components."""
        if self._browser:
            await self._browser.disconnect()
        
        linkedin = get_linkedin_client()
        await linkedin.close()
        
        self._initialized = False
        logger.info('Automation orchestrator shutdown')
    
    # Browser automation
    async def navigate(self, url: str) -> bool:
        if not self._browser:
            return False
        return await self._browser.navigate(url)
    
    async def screenshot(self, path: str) -> bool:
        if not self._browser:
            return False
        return await self._browser.screenshot(path)
    
    async def save_browser_session(self, name: str):
        if not self._browser:
            return None
        return await self._browser.save_session(name)
    
    async def restore_browser_session(self, name: str) -> bool:
        if not self._browser:
            return False
        session = load_session(name)
        if session:
            return await self._browser.restore_session(session)
        return False
    
    # Credential access
    async def get_credential(self, service: str, account: str):
        mgr = get_credential_manager()
        return await mgr.get_credential(service, account)
    
    # X (Twitter) automation
    async def x_post(self, account_id: str, text: str) -> bool:
        """Post to X from specific account."""
        mgr = get_x_manager()
        token = await mgr.get_token(account_id)
        if not token:
            logger.error(f'No token for X account {account_id}')
            return False
        
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://api.twitter.com/2/tweets',
                headers={'Authorization': f'Bearer {token.access_token}', 'Content-Type': 'application/json'},
                json={'text': text}
            ) as resp:
                if resp.status == 201:
                    logger.info(f'Posted to X as {account_id}')
                    return True
                logger.error(f'X post failed: {await resp.text()}')
                return False
    
    async def list_x_accounts(self) -> List[str]:
        return await get_x_manager().list_accounts()
    
    # Google automation
    async def google_get_token(self, email: str):
        return await get_google_manager().get_token(email)
    
    async def list_google_accounts(self) -> List[str]:
        return await get_google_manager().list_accounts()
    
    # LinkedIn automation
    async def linkedin_post(self, text: str) -> bool:
        client = get_linkedin_client()
        if not await client.load_session():
            logger.warning('LinkedIn session not available')
            return False
        return await client.post_update(text)
    
    # Windows automation
    async def click_screen(self, x: int, y: int) -> bool:
        gui = get_gui_automation()
        return await gui.click(x, y)
    
    async def type_text(self, text: str) -> bool:
        gui = get_gui_automation()
        return await gui.type_text(text)
    
    async def take_screenshot(self, path: str = None) -> bytes:
        gui = get_gui_automation()
        return await gui.screenshot(path)
    
    # Task scheduling
    async def schedule_task(self, name: str, command: str, schedule: str = 'HOURLY') -> bool:
        scheduler = get_task_scheduler()
        return await scheduler.create_task(name, command, schedule)
    
    async def list_scheduled_tasks(self) -> List[Dict]:
        scheduler = get_task_scheduler()
        return await scheduler.list_tasks()
    
    # Wake-on-LAN
    async def wake_computer(self, name: str, wait: bool = False) -> bool:
        wol = get_wol_manager()
        return await wol.wake(name, wait=wait)
    
    def register_computer(self, name: str, mac: str, host: str):
        wol = get_wol_manager()
        wol.add_computer(name, mac, host)


# Singleton
_orchestrator: Optional[AutomationOrchestrator] = None

def get_orchestrator() -> AutomationOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AutomationOrchestrator()
    return _orchestrator


async def main():
    """Example usage."""
    orch = get_orchestrator()
    await orch.initialize()
    
    # List available accounts
    x_accounts = await orch.list_x_accounts()
    print(f'X accounts: {x_accounts}')
    
    google_accounts = await orch.list_google_accounts()
    print(f'Google accounts: {google_accounts}')
    
    # Take screenshot
    await orch.screenshot('/tmp/screen.png')
    
    await orch.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
