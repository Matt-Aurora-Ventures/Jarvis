"""
Windows Task Scheduler integration.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WindowsTaskScheduler:
    def __init__(self, prefix: str = 'Jarvis'):
        self.prefix = prefix
    
    async def _run_schtasks(self, args: List[str]) -> tuple:
        try:
            proc = await asyncio.create_subprocess_exec(
                'schtasks', *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode == 0, stdout.decode(), stderr.decode()
        except Exception as e:
            logger.error(f'schtasks error: {e}')
            return False, '', str(e)
    
    async def create_task(
        self,
        name: str,
        command: str,
        schedule: str = 'HOURLY',
        start_time: str = '00:00',
        run_as_system: bool = False
    ) -> bool:
        task_name = f'{self.prefix}-{name}'
        
        args = [
            '/Create',
            '/TN', task_name,
            '/TR', command,
            '/SC', schedule,
            '/ST', start_time,
            '/F'
        ]
        
        if run_as_system:
            args.extend(['/RU', 'SYSTEM'])
        
        success, stdout, stderr = await self._run_schtasks(args)
        
        if success:
            logger.info(f'Created scheduled task: {task_name}')
        else:
            logger.error(f'Failed to create task: {stderr}')
        
        return success
    
    async def delete_task(self, name: str) -> bool:
        task_name = f'{self.prefix}-{name}'
        success, _, stderr = await self._run_schtasks(['/Delete', '/TN', task_name, '/F'])
        if success:
            logger.info(f'Deleted scheduled task: {task_name}')
        return success
    
    async def run_task(self, name: str) -> bool:
        task_name = f'{self.prefix}-{name}'
        success, _, stderr = await self._run_schtasks(['/Run', '/TN', task_name])
        if success:
            logger.info(f'Running task: {task_name}')
        return success
    
    async def list_tasks(self) -> List[Dict[str, Any]]:
        success, stdout, _ = await self._run_schtasks(['/Query', '/FO', 'CSV', '/V'])
        
        if not success:
            return []
        
        tasks = []
        lines = stdout.strip().split(chr(10))  # Use chr(10) for newline
        
        if len(lines) < 2:
            return []
        
        headers = [h.strip('"') for h in lines[0].split(',')]
        
        for line in lines[1:]:
            if self.prefix not in line:
                continue
            
            values = [v.strip('"') for v in line.split(',')]
            if len(values) == len(headers):
                task = dict(zip(headers, values))
                tasks.append(task)
        
        return tasks
    
    async def get_task_status(self, name: str) -> Optional[str]:
        task_name = f'{self.prefix}-{name}'
        success, stdout, _ = await self._run_schtasks(['/Query', '/TN', task_name, '/FO', 'CSV', '/V'])
        
        if not success:
            return None
        
        lines = stdout.strip().split(chr(10))
        if len(lines) < 2:
            return None
        
        for line in lines[1:]:
            if task_name in line:
                parts = line.split(',')
                for part in parts:
                    if 'Running' in part or 'Ready' in part or 'Disabled' in part:
                        return part.strip('"')
        
        return 'Unknown'
    
    async def enable_task(self, name: str) -> bool:
        task_name = f'{self.prefix}-{name}'
        success, _, _ = await self._run_schtasks(['/Change', '/TN', task_name, '/ENABLE'])
        return success
    
    async def disable_task(self, name: str) -> bool:
        task_name = f'{self.prefix}-{name}'
        success, _, _ = await self._run_schtasks(['/Change', '/TN', task_name, '/DISABLE'])
        return success


_scheduler: Optional[WindowsTaskScheduler] = None

def get_task_scheduler() -> WindowsTaskScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = WindowsTaskScheduler()
    return _scheduler
