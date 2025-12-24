"""
Lightweight storage utilities using txt files instead of JSON.
Optimized for minimal storage and maximum performance.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class TxtStorage:
    """Lightweight text-based storage system."""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_txt(self, filename: str, data: Union[str, Dict, List]) -> bool:
        """Save data as compact txt file."""
        try:
            filepath = self.storage_dir / f"{filename}.txt"
            
            if isinstance(data, str):
                content = data
            elif isinstance(data, dict):
                # Convert dict to compact format
                content = self._dict_to_txt(data)
            elif isinstance(data, list):
                # Convert list to compact format
                content = self._list_to_txt(data)
            else:
                content = str(data)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Failed to save txt file {filename}: {e}")
            return False
    
    def load_txt(self, filename: str, data_type: str = "string") -> Union[str, Dict, List, None]:
        """Load data from txt file."""
        try:
            filepath = self.storage_dir / f"{filename}.txt"
            if not filepath.exists():
                return None
            
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            
            if data_type == "string":
                return content
            elif data_type == "dict":
                return self._txt_to_dict(content)
            elif data_type == "list":
                return self._txt_to_list(content)
            else:
                return content
        except Exception as e:
            print(f"Failed to load txt file {filename}: {e}")
            return None
    
    def append_txt(self, filename: str, data: Union[str, Dict, List]) -> bool:
        """Append data to txt file."""
        try:
            filepath = self.storage_dir / f"{filename}.txt"
            
            if isinstance(data, str):
                content = data
            elif isinstance(data, dict):
                content = self._dict_to_txt(data)
            elif isinstance(data, list):
                content = self._list_to_txt(data)
            else:
                content = str(data)
            
            with open(filepath, "a", encoding="utf-8") as f:
                f.write("\n" + content)
            return True
        except Exception as e:
            print(f"Failed to append to txt file {filename}: {e}")
            return False
    
    def _dict_to_txt(self, data: Dict[str, Any]) -> str:
        """Convert dict to compact txt format."""
        lines = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{key}:{json.dumps(value)}")
            else:
                lines.append(f"{key}:{value}")
        return "\n".join(lines)
    
    def _txt_to_dict(self, content: str) -> Dict[str, Any]:
        """Convert txt content back to dict."""
        data = {}
        for line in content.strip().split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                try:
                    # Try to parse as JSON first
                    data[key] = json.loads(value)
                except Exception as e:
                    # Fall back to string
                    data[key] = value
        return data
    
    def _list_to_txt(self, data: List[Any]) -> str:
        """Convert list to compact txt format."""
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(json.dumps(item))
            else:
                lines.append(str(item))
        return "\n".join(lines)
    
    def _txt_to_list(self, content: str) -> List[Any]:
        """Convert txt content back to list."""
        items = []
        for line in content.strip().split("\n"):
            if line.strip():
                try:
                    # Try to parse as JSON first
                    items.append(json.loads(line))
                except Exception as e:
                    # Fall back to string
                    items.append(line)
        return items
    
    def log_event(self, filename: str, event_type: str, details: Dict[str, Any]) -> bool:
        """Log an event with timestamp."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "details": details
        }
        return self.append_txt(filename, log_entry)
    
    def get_latest_entries(self, filename: str, count: int = 10) -> List[Dict[str, Any]]:
        """Get latest entries from log file."""
        content = self.load_txt(filename, "list")
        if not content:
            return []
        
        # Return last N entries
        return content[-count:] if len(content) >= count else content
    
    def save_md(self, key: str, content: str) -> bool:
        """Save markdown content."""
        try:
            file_path = self.storage_dir / f"{key}.md"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Failed to save markdown: {e}")
            return False
    
    def clear_file(self, filename: str) -> bool:
        """Clear a storage file."""
        try:
            filepath = self.storage_dir / f"{filename}.txt"
            if filepath.exists():
                filepath.unlink()
            return True
        except Exception as e:
            print(f"Failed to clear file: {e}")
            return False
    
    def file_exists(self, filename: str) -> bool:
        """Check if file exists."""
        return (self.storage_dir / f"{filename}.txt").exists()
    
    def get_file_size(self, filename: str) -> int:
        """Get file size in bytes."""
        try:
            return (self.storage_dir / f"{filename}.txt").stat().st_size
        except Exception as e:
            print(f"Failed to get file size: {e}")
            return 0


class CompactMarkdownStorage:
    """Ultra-compact markdown storage for documentation."""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_compact_md(self, filename: str, title: str, sections: Dict[str, str]) -> bool:
        """Save as compact markdown."""
        try:
            filepath = self.storage_dir / f"{filename}.md"
            
            content = f"# {title}\n\n"
            for section_title, section_content in sections.items():
                content += f"## {section_title}\n{section_content}\n\n"
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            return False
    
    def append_section(self, filename: str, section_title: str, content: str) -> bool:
        """Append section to existing markdown."""
        try:
            filepath = self.storage_dir / f"{filename}.md"
            
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"\n## {section_title}\n{content}\n")
            return True
        except Exception as e:
            return False


# Global storage instances
_storage_instances = {}


def get_storage(storage_dir: Union[str, Path]) -> TxtStorage:
    """Get or create storage instance."""
    storage_dir = Path(storage_dir)
    key = str(storage_dir)
    
    if key not in _storage_instances:
        _storage_instances[key] = TxtStorage(storage_dir)
    
    return _storage_instances[key]


def get_md_storage(storage_dir: Union[str, Path]) -> CompactMarkdownStorage:
    """Get or create markdown storage instance."""
    storage_dir = Path(storage_dir)
    key = f"md_{storage_dir}"
    
    if key not in _storage_instances:
        _storage_instances[key] = CompactMarkdownStorage(storage_dir)
    
    return _storage_instances[key]
