"""LanceDB vector store for AI memory and semantic search."""
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

try:
    import lancedb
    HAS_LANCEDB = True
except ImportError:
    HAS_LANCEDB = False
    lancedb = None


@dataclass
class Document:
    """A document to store in the vector database."""
    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class SearchResult:
    """Result from a vector search."""
    document: Document
    score: float
    distance: float


class VectorStore:
    """
    LanceDB-based vector store for semantic search and AI memory.
    
    LanceDB is:
    - Embedded (no server needed)
    - Fast (Rust-based)
    - Supports automatic embedding
    - Serverless-friendly
    """
    
    def __init__(
        self,
        db_path: str = "data/vectordb",
        table_name: str = "memory",
        embedding_dim: int = 1536,  # OpenAI ada-002 dimension
    ):
        self.db_path = Path(db_path)
        self.table_name = table_name
        self.embedding_dim = embedding_dim
        self._db = None
        self._table = None
        
        if not HAS_LANCEDB:
            logger.warning("LanceDB not installed. Vector store disabled.")
            return
        
        self._init_db()
    
    def _init_db(self):
        """Initialize the database and table."""
        if not HAS_LANCEDB:
            return
        
        self.db_path.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self.db_path))
        
        # Check if table exists
        if self.table_name in self._db.table_names():
            self._table = self._db.open_table(self.table_name)
            logger.info(f"Opened existing table: {self.table_name}")
        else:
            logger.info(f"Table {self.table_name} will be created on first insert")
    
    def add(self, documents: List[Document]) -> int:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of documents with embeddings
            
        Returns:
            Number of documents added
        """
        if not HAS_LANCEDB or not self._db:
            return 0
        
        data = []
        for doc in documents:
            if doc.embedding is None:
                logger.warning(f"Document {doc.id} has no embedding, skipping")
                continue
            
            data.append({
                "id": doc.id,
                "text": doc.text,
                "vector": doc.embedding,
                "metadata": doc.metadata,
                "created_at": doc.created_at,
            })
        
        if not data:
            return 0
        
        if self._table is None:
            self._table = self._db.create_table(self.table_name, data)
        else:
            self._table.add(data)
        
        logger.info(f"Added {len(data)} documents to vector store")
        return len(data)
    
    def search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """
        Search for similar documents.
        
        Args:
            query_embedding: Query vector
            limit: Maximum results to return
            filter_metadata: Optional metadata filter
            
        Returns:
            List of search results sorted by relevance
        """
        if not HAS_LANCEDB or self._table is None:
            return []
        
        try:
            query = self._table.search(query_embedding).limit(limit)
            
            results = query.to_list()
            
            search_results = []
            for row in results:
                doc = Document(
                    id=row["id"],
                    text=row["text"],
                    metadata=row.get("metadata", {}),
                    created_at=row.get("created_at", 0),
                )
                search_results.append(SearchResult(
                    document=doc,
                    score=1 - row.get("_distance", 0),  # Convert distance to similarity
                    distance=row.get("_distance", 0),
                ))
            
            return search_results
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def delete(self, doc_ids: List[str]) -> int:
        """Delete documents by ID."""
        if not HAS_LANCEDB or self._table is None:
            return 0
        
        try:
            filter_expr = " OR ".join([f'id = "{id}"' for id in doc_ids])
            self._table.delete(filter_expr)
            return len(doc_ids)
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return 0
    
    def count(self) -> int:
        """Get total document count."""
        if not HAS_LANCEDB or self._table is None:
            return 0
        return self._table.count_rows()
    
    def clear(self):
        """Clear all documents."""
        if not HAS_LANCEDB or self._db is None:
            return
        
        if self.table_name in self._db.table_names():
            self._db.drop_table(self.table_name)
            self._table = None
            logger.info(f"Cleared table: {self.table_name}")


class MemoryStore(VectorStore):
    """
    Specialized vector store for conversation memory.
    
    Stores conversation turns with semantic search capability.
    """
    
    def __init__(self, db_path: str = "data/memory_db"):
        super().__init__(db_path=db_path, table_name="conversations")
    
    def add_memory(
        self,
        text: str,
        embedding: List[float],
        role: str = "user",
        conversation_id: Optional[str] = None,
        importance: float = 0.5,
    ) -> str:
        """Add a memory entry."""
        import uuid
        
        doc_id = str(uuid.uuid4())[:8]
        doc = Document(
            id=doc_id,
            text=text,
            embedding=embedding,
            metadata={
                "role": role,
                "conversation_id": conversation_id,
                "importance": importance,
            }
        )
        
        self.add([doc])
        return doc_id
    
    def recall(
        self,
        query_embedding: List[float],
        limit: int = 5,
        min_importance: float = 0.0,
    ) -> List[SearchResult]:
        """Recall relevant memories."""
        results = self.search(query_embedding, limit=limit * 2)
        
        # Filter by importance
        filtered = [
            r for r in results
            if r.document.metadata.get("importance", 0) >= min_importance
        ]
        
        return filtered[:limit]
