"""Memory system configuration with environment overrides."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

@dataclass
class MemoryConfig:
    """Configuration for the Jarvis memory system."""

    # Root directory for memory workspace
    memory_root: Path = field(default_factory=lambda: Path.home() / ".lifeos" / "memory")

    # SQLite database filename
    db_name: str = "jarvis.db"

    # PostgreSQL connection (from environment)
    postgres_url: Optional[str] = field(default_factory=lambda: os.getenv("DATABASE_URL"))

    # Daily log archival threshold (days)
    archive_after_days: int = 30

    # FTS5 tokenizer configuration
    fts_tokenizer: str = "porter unicode61"

    # WAL mode for concurrent access
    enable_wal: bool = True

    # Embedding model (for PostgreSQL integration)
    embedding_model: str = "BAAI/bge-large-en-v1.5"

    @property
    def db_path(self) -> Path:
        """Full path to SQLite database."""
        return self.memory_root / self.db_name

    @property
    def daily_logs_dir(self) -> Path:
        """Directory for daily session logs."""
        return self.memory_root / "memory"

    @property
    def archives_dir(self) -> Path:
        """Directory for archived logs."""
        return self.memory_root / "memory" / "archives"

    @property
    def bank_dir(self) -> Path:
        """Directory for knowledge bank."""
        return self.memory_root / "bank"

    @property
    def entities_dir(self) -> Path:
        """Directory for entity profiles."""
        return self.memory_root / "bank" / "entities"


_config: Optional[MemoryConfig] = None


def get_config() -> MemoryConfig:
    """Get or create the global memory configuration."""
    global _config
    if _config is None:
        # Allow environment override for memory root
        root_override = os.getenv("JARVIS_MEMORY_ROOT")
        if root_override:
            _config = MemoryConfig(memory_root=Path(root_override))
        else:
            _config = MemoryConfig()
    return _config
