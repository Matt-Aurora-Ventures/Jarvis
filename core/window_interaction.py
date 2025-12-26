"""
Window Interaction Module for Jarvis

Provides functionality to interact with browser windows and elements.
"""

import pyautogui
import pygetwindow as gw
import time
from typing import Optional, Dict, List, Tuple
import logging
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add a small delay between actions to prevent overwhelming the system
pyautogui.PAUSE = 0.5
pyautogui.FAILSAFE = True

@dataclass
class WindowInfo:
    """Class to store window information."""
    title: str
    handle: int
    width: int
    height: int
    x: int
    y: int

class WindowInteractor:
    """Handles interaction with browser windows and elements."""
    
    def __init__(self):
        self.active_window = None
        self.browser_windows = []
        self.last_interaction = None
        
    def list_browser_windows(self) -> List[WindowInfo]:
        """List all open browser windows."""
        browsers = ['chrome', 'firefox', 'safari', 'edge', 'brave']
        windows = []
        
        for window in gw.getAllWindows():
            if any(browser in window.title.lower() for browser in browsers):
                win_info = WindowInfo(
                    title=window.title,
                    handle=window._hWnd,
                    width=window.width,
                    height=window.height,
                    x=window.left,
                    y=window.top
                )
                windows.append(win_info)
                
        self.browser_windows = windows
        return windows
    
    def activate_window(self, title_contains: str) -> bool:
        """Activate a browser window by title."""
        try:
            window = gw.getWindowsWithTitle(title_contains)[0]
            if window:
                window.activate()
                self.active_window = window
                time.sleep(1)  # Give the window time to come to foreground
                return True
        except Exception as e:
            logger.error(f"Failed to activate window '{title_contains}': {e}")
        return False
    
    def click_element(self, x: int, y: int, button: str = 'left', clicks: int = 1) -> bool:
        """Click at specific coordinates."""
        try:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            self.last_interaction = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to click at ({x}, {y}): {e}")
            return False
    
    def find_and_click(self, image_path: str, confidence: float = 0.9) -> bool:
        """Find and click on an image on screen."""
        try:
            location = pyautogui.locateOnScreen(image_path, confidence=confidence)
            if location:
                center = pyautogui.center(location)
                pyautogui.click(center)
                self.last_interaction = time.time()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to find and click {image_path}: {e}")
            return False
    
    def type_text(self, text: str, interval: float = 0.1) -> bool:
        """Type text at the current cursor position."""
        try:
            pyautogui.typewrite(text, interval=interval)
            self.last_interaction = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to type text: {e}")
            return False
    
    def press_key(self, key: str) -> bool:
        """Press a key."""
        try:
            pyautogui.press(key)
            self.last_interaction = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to press key {key}: {e}")
            return False
    
    def scroll(self, clicks: int) -> bool:
        """Scroll the mouse wheel."""
        try:
            pyautogui.scroll(clicks)
            self.last_interaction = time.time()
            return True
        except Exception as e:
            logger.error(f"Failed to scroll: {e}")
            return False
    
    def get_screen_size(self) -> Tuple[int, int]:
        """Get the screen size."""
        return pyautogui.size()
    
    def get_mouse_position(self) -> Tuple[int, int]:
        """Get the current mouse position."""
        return pyautogui.position()
    
    def move_mouse(self, x: int, y: int, duration: float = 0.5) -> bool:
        """Move the mouse to specific coordinates."""
        try:
            pyautogui.moveTo(x, y, duration=duration)
            return True
        except Exception as e:
            logger.error(f"Failed to move mouse to ({x}, {y}): {e}")
            return False

# Global window interactor instance
_window_interactor = None

def get_window_interactor() -> WindowInteractor:
    """Get the global window interactor instance."""
    global _window_interactor
    if _window_interactor is None:
        _window_interactor = WindowInteractor()
    return _window_interactor
