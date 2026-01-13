"""uvloop integration for faster async performance."""
import sys
import logging

logger = logging.getLogger(__name__)


def install_uvloop() -> bool:
    """
    Install uvloop as the default event loop policy.
    
    uvloop is a fast, drop-in replacement for asyncio's event loop.
    It provides 2-4x performance improvement for async operations.
    
    Note: uvloop only works on Unix systems (Linux, macOS).
    On Windows, this is a no-op.
    
    Returns:
        bool: True if uvloop was installed, False otherwise
    """
    if sys.platform == "win32":
        logger.debug("uvloop not available on Windows, using default asyncio")
        return False
    
    try:
        import uvloop
        uvloop.install()
        logger.info("uvloop installed as default event loop")
        return True
    except ImportError:
        logger.debug("uvloop not installed, using default asyncio")
        return False
    except Exception as e:
        logger.warning(f"Failed to install uvloop: {e}")
        return False


def get_event_loop_policy():
    """Get the appropriate event loop policy for the platform."""
    if sys.platform == "win32":
        import asyncio
        return asyncio.WindowsSelectorEventLoopPolicy()
    
    try:
        import uvloop
        return uvloop.EventLoopPolicy()
    except ImportError:
        import asyncio
        return asyncio.DefaultEventLoopPolicy()
