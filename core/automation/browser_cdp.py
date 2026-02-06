"""
Browser CDP Automation - Connect to Chrome via DevTools Protocol.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp

from core.automation.interfaces import BrowserAutomator, BrowserSession

logger = logging.getLogger(__name__)

SESSION_STORE_PATH = Path(__file__).parent.parent.parent / 'data' / 'browser_sessions'
SESSION_STORE_PATH.mkdir(parents=True, exist_ok=True)


class ChromeCDPClient(BrowserAutomator):
    """Chrome DevTools Protocol client."""
    
    def __init__(self):
        self.debug_url: Optional[str] = None
        self.ws_url: Optional[str] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._message_id = 0
        self._responses: Dict[int, asyncio.Future] = {}

    async def connect(self, debug_port: int = 9222) -> bool:
        self.debug_url = f'http://127.0.0.1:{debug_port}'
        try:
            self._session = aiohttp.ClientSession()
            async with self._session.get(f'{self.debug_url}/json/version') as resp:
                if resp.status != 200:
                    return False
                info = await resp.json()
                self.ws_url = info.get('webSocketDebuggerUrl')
            
            if not self.ws_url:
                return False
            
            self._ws = await self._session.ws_connect(self.ws_url)
            asyncio.create_task(self._message_handler())
            logger.info(f'Connected to Chrome CDP')
            return True
        except Exception as e:
            logger.error(f'CDP connection failed: {e}')
            return False
    
    async def disconnect(self) -> None:
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
    
    async def _message_handler(self):
        if not self._ws:
            return
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                msg_id = data.get('id')
                if msg_id and msg_id in self._responses:
                    self._responses[msg_id].set_result(data)
    
    async def _send_command(self, method: str, params: Dict = None) -> Dict:
        if not self._ws:
            raise RuntimeError('Not connected')
        
        self._message_id += 1
        msg_id = self._message_id
        message = {'id': msg_id, 'method': method, 'params': params or {}}
        
        future = asyncio.get_event_loop().create_future()
        self._responses[msg_id] = future
        await self._ws.send_json(message)
        
        try:
            result = await asyncio.wait_for(future, timeout=30)
            return result.get('result', {})
        finally:
            del self._responses[msg_id]

    async def navigate(self, url: str, wait_until: str = 'load') -> bool:
        try:
            await self._send_command('Page.enable')
            result = await self._send_command('Page.navigate', {'url': url})
            await asyncio.sleep(2)
            return 'errorText' not in result
        except Exception as e:
            logger.error(f'Navigation error: {e}')
            return False
    
    async def screenshot(self, path: str, full_page: bool = False) -> bool:
        try:
            import base64
            await self._send_command('Page.enable')
            result = await self._send_command('Page.captureScreenshot', {'format': 'png'})
            Path(path).write_bytes(base64.b64decode(result.get('data', '')))
            return True
        except Exception as e:
            logger.error(f'Screenshot error: {e}')
            return False
    
    async def get_cookies(self) -> List[Dict[str, Any]]:
        await self._send_command('Network.enable')
        result = await self._send_command('Network.getAllCookies')
        return result.get('cookies', [])
    
    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> bool:
        await self._send_command('Network.enable')
        await self._send_command('Network.setCookies', {'cookies': cookies})
        return True
    
    async def execute_script(self, script: str) -> Any:
        try:
            await self._send_command('Runtime.enable')
            result = await self._send_command('Runtime.evaluate', {
                'expression': script, 'returnByValue': True
            })
            return result.get('result', {}).get('value')
        except Exception:
            return None
    
    async def click(self, selector: str) -> bool:
        script = f'document.querySelector({json.dumps(selector)})?.click() || false'
        return bool(await self.execute_script(script))
    
    async def type_text(self, selector: str, text: str) -> bool:
        script = f'(function(){{ var el=document.querySelector({json.dumps(selector)}); if(el){{el.value={json.dumps(text)}; return true;}} return false; }})()'
        return bool(await self.execute_script(script))

    async def save_session(self, name: str) -> BrowserSession:
        cookies = await self.get_cookies()
        local_storage = await self.execute_script('JSON.stringify(Object.fromEntries(Object.entries(localStorage)))') or '{}'
        session_storage = await self.execute_script('JSON.stringify(Object.fromEntries(Object.entries(sessionStorage)))') or '{}'
        user_agent = (await self._send_command('Browser.getVersion')).get('userAgent', '')
        
        session = BrowserSession(
            cookies=cookies,
            local_storage=json.loads(local_storage) if isinstance(local_storage, str) else {},
            session_storage=json.loads(session_storage) if isinstance(session_storage, str) else {},
            user_agent=user_agent,
            created_at=datetime.utcnow(),
            last_used=datetime.utcnow(),
            domain=name
        )
        
        session_file = SESSION_STORE_PATH / f'{name}.json'
        session_file.write_text(json.dumps({
            'cookies': session.cookies,
            'local_storage': session.local_storage,
            'session_storage': session.session_storage,
            'user_agent': session.user_agent,
            'created_at': session.created_at.isoformat(),
            'last_used': session.last_used.isoformat(),
            'domain': session.domain
        }, indent=2))
        
        logger.info(f'Session saved: {name}')
        return session
    
    async def restore_session(self, session: BrowserSession) -> bool:
        try:
            await self.set_cookies(session.cookies)
            for key, value in (session.local_storage or {}).items():
                await self.execute_script(f'localStorage.setItem({json.dumps(key)}, {json.dumps(value)})')
            for key, value in (session.session_storage or {}).items():
                await self.execute_script(f'sessionStorage.setItem({json.dumps(key)}, {json.dumps(value)})')
            return True
        except Exception as e:
            logger.error(f'Restore error: {e}')
            return False


def load_session(name: str) -> Optional[BrowserSession]:
    session_file = SESSION_STORE_PATH / f'{name}.json'
    if not session_file.exists():
        return None
    try:
        data = json.loads(session_file.read_text())
        return BrowserSession(
            cookies=data['cookies'],
            local_storage=data.get('local_storage', {}),
            session_storage=data.get('session_storage', {}),
            user_agent=data.get('user_agent', ''),
            created_at=datetime.fromisoformat(data['created_at']),
            last_used=datetime.fromisoformat(data['last_used']),
            domain=data.get('domain', name)
        )
    except Exception as e:
        logger.error(f'Load session error: {e}')
        return None


async def launch_chrome_with_debugging(port: int = 9222) -> bool:
    import subprocess
    chrome_paths = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe'
    ]
    for path in chrome_paths:
        if Path(path).exists():
            subprocess.Popen([path, f'--remote-debugging-port={port}', '--user-data-dir=' + str(Path.home() / '.chrome-automation')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(3)
            return True
    return False
