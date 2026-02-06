"""
Remote Log Monitoring for ClawdBots
Watches /var/log/clawdbot/ for errors and anomalies.
"""
import os
import re
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter

logger = logging.getLogger(__name__)

LOG_DIR = Path('/var/log/clawdbot')


class LogMonitor:
    def __init__(self):
        self.log_dir = LOG_DIR
    
    def get_error_summary(self, hours: int = 24) -> dict:
        """Get error counts per bot for the last N hours."""
        summary = {}
        for log_file in self.log_dir.glob('*.log'):
            bot_name = log_file.stem
            errors = self._count_pattern(log_file, 'ERROR', hours)
            warnings = self._count_pattern(log_file, 'WARNING', hours)
            summary[bot_name] = {
                'errors': errors,
                'warnings': warnings,
                'last_activity': self._last_line_time(log_file)
            }
        return summary
    
    def get_recent_errors(self, bot: str = None, limit: int = 10) -> list:
        """Get recent error messages."""
        errors = []
        files = [self.log_dir / f'{bot}.log'] if bot else self.log_dir.glob('*.log')
        
        for log_file in files:
            if not log_file.exists():
                continue
            try:
                lines = log_file.read_text().split('\n')
                for line in reversed(lines):
                    if 'ERROR' in line:
                        errors.append({
                            'bot': log_file.stem,
                            'message': line.strip()[:200],
                            'timestamp': self._extract_timestamp(line)
                        })
                        if len(errors) >= limit:
                            break
            except Exception as e:
                logger.error(f'Error reading {log_file}: {e}')
        
        return sorted(errors, key=lambda x: x.get('timestamp', ''), reverse=True)[:limit]
    
    def get_health_report(self) -> str:
        """Generate a formatted health report from logs."""
        summary = self.get_error_summary(24)
        lines = ['📊 **Log Health Report (24h)**\n']
        
        for bot, data in sorted(summary.items()):
            status = '✅' if data['errors'] == 0 else '⚠️' if data['errors'] < 5 else '🔴'
            lines.append(f'{status} **{bot}**: {data["errors"]} errors, {data["warnings"]} warnings')
            if data['last_activity']:
                lines.append(f'   Last activity: {data["last_activity"]}')
        
        total_errors = sum(d['errors'] for d in summary.values())
        if total_errors > 0:
            lines.append(f'\n🔴 **Total: {total_errors} errors** - Run /errors for details')
        else:
            lines.append('\n✅ **All clear** - no errors in last 24 hours')
        
        return '\n'.join(lines)
    
    def detect_anomalies(self) -> list:
        """Detect log anomalies: repeated errors, sudden spikes, silent bots."""
        anomalies = []
        summary = self.get_error_summary(1)  # Last hour
        
        for bot, data in summary.items():
            # Error spike: more than 10 errors in 1 hour
            if data['errors'] > 10:
                anomalies.append({
                    'type': 'error_spike',
                    'bot': bot,
                    'count': data['errors'],
                    'severity': 'high'
                })
            
            # Silent bot: no activity in last hour
            if data['last_activity']:
                try:
                    last = datetime.fromisoformat(data['last_activity'])
                    if datetime.now() - last > timedelta(hours=1):
                        anomalies.append({
                            'type': 'silent_bot',
                            'bot': bot,
                            'last_seen': data['last_activity'],
                            'severity': 'medium'
                        })
                except (ValueError, TypeError):
                    pass
        
        return anomalies
    
    def _count_pattern(self, log_file: Path, pattern: str, hours: int) -> int:
        if not log_file.exists():
            return 0
        try:
            cutoff = datetime.now() - timedelta(hours=hours)
            count = 0
            for line in log_file.read_text().split('\n'):
                if pattern in line:
                    ts = self._extract_timestamp(line)
                    if ts:
                        try:
                            if datetime.fromisoformat(ts.replace(',', '.')) >= cutoff:
                                count += 1
                        except (ValueError, TypeError):
                            count += 1  # Count if can't parse timestamp
                    else:
                        count += 1
            return count
        except Exception:
            return 0
    
    def _last_line_time(self, log_file: Path) -> str:
        if not log_file.exists():
            return None
        try:
            lines = log_file.read_text().strip().split('\n')
            for line in reversed(lines):
                ts = self._extract_timestamp(line)
                if ts:
                    return ts
        except Exception:
            pass
        return None
    
    def _extract_timestamp(self, line: str) -> str:
        match = re.match(r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})', line)
        return match.group(1) if match else None
