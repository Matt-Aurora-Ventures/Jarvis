"""Log aggregation and analysis."""
import json
import gzip
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List
from collections import defaultdict, Counter


class LogAggregator:
    """Aggregate and analyze logs."""
    
    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or Path("logs")
    
    def aggregate_daily(self, date: datetime = None) -> Dict:
        date = date or datetime.utcnow()
        log_file = self.log_dir / f"app-{date.strftime('%Y-%m-%d')}.log"
        
        if not log_file.exists():
            return {"total": 0, "errors": 0, "warnings": 0}
        
        stats = {"total": 0, "errors": 0, "warnings": 0, "by_module": {}, "by_hour": defaultdict(int)}
        
        with open(log_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    stats["total"] += 1
                    level = entry.get("level", "")
                    if level == "ERROR":
                        stats["errors"] += 1
                    elif level == "WARNING":
                        stats["warnings"] += 1
                    
                    module = entry.get("module", "unknown")
                    stats["by_module"][module] = stats["by_module"].get(module, 0) + 1
                    
                    ts = entry.get("timestamp", "")[:13]
                    stats["by_hour"][ts] += 1
                except json.JSONDecodeError:
                    continue
        
        stats["by_hour"] = dict(stats["by_hour"])
        return stats
    
    def get_error_summary(self, days: int = 7) -> Dict:
        errors = []
        for i in range(days):
            date = datetime.utcnow() - timedelta(days=i)
            log_file = self.log_dir / f"app-{date.strftime('%Y-%m-%d')}.log"
            if log_file.exists():
                with open(log_file) as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if entry.get("level") == "ERROR":
                                errors.append(entry.get("message", "")[:100])
                        except json.JSONDecodeError:
                            continue
        
        return {"total": len(errors), "top_errors": Counter(errors).most_common(10)}
    
    def compress_old_logs(self, days_old: int = 7) -> int:
        cutoff = datetime.utcnow() - timedelta(days=days_old)
        compressed = 0
        
        for log_file in self.log_dir.glob("*.log"):
            if log_file.stat().st_mtime < cutoff.timestamp():
                with open(log_file, 'rb') as f_in:
                    with gzip.open(f"{log_file}.gz", 'wb') as f_out:
                        f_out.writelines(f_in)
                log_file.unlink()
                compressed += 1
        
        return compressed
    
    def search(self, query: str, days: int = 1, level: str = None) -> List[Dict]:
        results = []
        query_lower = query.lower()
        
        for i in range(days):
            date = datetime.utcnow() - timedelta(days=i)
            log_file = self.log_dir / f"app-{date.strftime('%Y-%m-%d')}.log"
            if log_file.exists():
                with open(log_file) as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            if level and entry.get("level") != level:
                                continue
                            if query_lower in json.dumps(entry).lower():
                                results.append(entry)
                        except json.JSONDecodeError:
                            continue
        
        return results[:1000]
