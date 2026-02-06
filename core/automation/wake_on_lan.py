"""
Wake-on-LAN functionality for remote computer wake.
"""

import asyncio
import logging
import socket
from typing import Optional

logger = logging.getLogger(__name__)


def create_magic_packet(mac_address: str) -> bytes:
    """Create Wake-on-LAN magic packet."""
    mac = mac_address.replace(':', '').replace('-', '').replace('.', '')
    
    if len(mac) != 12:
        raise ValueError(f'Invalid MAC address: {mac_address}')
    
    mac_bytes = bytes.fromhex(mac)
    # Magic packet: 6 bytes of 0xFF + 16 repetitions of MAC
    magic_packet = bytes([0xff] * 6) + mac_bytes * 16
    
    return magic_packet


async def send_wol(mac_address: str, broadcast: str = '255.255.255.255', port: int = 9) -> bool:
    try:
        packet = create_magic_packet(mac_address)
        
        loop = asyncio.get_event_loop()
        
        def send_packet():
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.sendto(packet, (broadcast, port))
        
        await loop.run_in_executor(None, send_packet)
        logger.info(f'WoL packet sent to {mac_address}')
        return True
    except Exception as e:
        logger.error(f'WoL error: {e}')
        return False


async def wake_and_wait(mac_address: str, host: str, timeout: int = 120, check_port: int = 22) -> bool:
    await send_wol(mac_address)
    
    start_time = asyncio.get_event_loop().time()
    
    while (asyncio.get_event_loop().time() - start_time) < timeout:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, check_port),
                timeout=5
            )
            writer.close()
            await writer.wait_closed()
            
            logger.info(f'Computer {host} is online')
            return True
        except (OSError, asyncio.TimeoutError):
            await asyncio.sleep(5)
    
    logger.warning(f'Computer {host} did not come online within {timeout}s')
    return False


class WakeOnLanManager:
    def __init__(self):
        self.computers: dict = {}
    
    def add_computer(self, name: str, mac_address: str, host: str):
        self.computers[name] = {'mac': mac_address, 'host': host}
    
    async def wake(self, name: str, wait: bool = False, timeout: int = 120) -> bool:
        if name not in self.computers:
            logger.error(f'Unknown computer: {name}')
            return False
        
        comp = self.computers[name]
        
        if wait:
            return await wake_and_wait(comp['mac'], comp['host'], timeout)
        else:
            return await send_wol(comp['mac'])
    
    async def wake_all(self) -> dict:
        results = {}
        for name in self.computers:
            results[name] = await self.wake(name)
        return results


_wol_manager: Optional[WakeOnLanManager] = None

def get_wol_manager() -> WakeOnLanManager:
    global _wol_manager
    if _wol_manager is None:
        _wol_manager = WakeOnLanManager()
    return _wol_manager
