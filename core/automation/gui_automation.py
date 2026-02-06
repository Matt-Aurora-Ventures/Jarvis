"""
Windows GUI Automation using PyAutoGUI.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    logger.warning('PyAutoGUI not installed')


class GUIAutomation:
    """Windows GUI automation wrapper."""
    
    def __init__(self):
        if not HAS_PYAUTOGUI:
            raise ImportError('PyAutoGUI is required: pip install pyautogui')
    
    async def click(self, x: int, y: int, button: str = 'left') -> bool:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: pyautogui.click(x, y, button=button)
            )
            return True
        except Exception as e:
            logger.error(f'Click error: {e}')
            return False
    
    async def double_click(self, x: int, y: int) -> bool:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: pyautogui.doubleClick(x, y)
            )
            return True
        except Exception as e:
            logger.error(f'Double click error: {e}')
            return False
    
    async def type_text(self, text: str, interval: float = 0.05) -> bool:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: pyautogui.write(text, interval=interval)
            )
            return True
        except Exception as e:
            logger.error(f'Type error: {e}')
            return False
    
    async def press_key(self, key: str) -> bool:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: pyautogui.press(key)
            )
            return True
        except Exception as e:
            logger.error(f'Press key error: {e}')
            return False
    
    async def hotkey(self, *keys: str) -> bool:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: pyautogui.hotkey(*keys)
            )
            return True
        except Exception as e:
            logger.error(f'Hotkey error: {e}')
            return False
    
    async def screenshot(self, path: Optional[str] = None) -> bytes:
        try:
            import io
            loop = asyncio.get_event_loop()
            img = await loop.run_in_executor(None, pyautogui.screenshot)
            
            if path:
                await loop.run_in_executor(None, lambda: img.save(path))
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()
        except Exception as e:
            logger.error(f'Screenshot error: {e}')
            return b''
    
    async def move_to(self, x: int, y: int, duration: float = 0.5) -> bool:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: pyautogui.moveTo(x, y, duration=duration)
            )
            return True
        except Exception as e:
            logger.error(f'Move error: {e}')
            return False
    
    async def scroll(self, clicks: int, x: int = None, y: int = None) -> bool:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: pyautogui.scroll(clicks, x=x, y=y)
            )
            return True
        except Exception as e:
            logger.error(f'Scroll error: {e}')
            return False
    
    async def locate_on_screen(self, image_path: str) -> Optional[Tuple[int, int]]:
        try:
            loop = asyncio.get_event_loop()
            location = await loop.run_in_executor(
                None, lambda: pyautogui.locateCenterOnScreen(image_path)
            )
            return location if location else None
        except Exception as e:
            logger.error(f'Locate error: {e}')
            return None
    
    def get_screen_size(self) -> Tuple[int, int]:
        return pyautogui.size()
    
    def get_mouse_position(self) -> Tuple[int, int]:
        return pyautogui.position()


_gui: Optional[GUIAutomation] = None

def get_gui_automation() -> GUIAutomation:
    global _gui
    if _gui is None:
        _gui = GUIAutomation()
    return _gui
