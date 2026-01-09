"""
BM25 Retrieval for Jarvis Memory Store.

Implements Okapi BM25 ranking algorithm without external dependencies.
BM25 is the industry standard for keyword-based retrieval (used in Elasticsearch, Lucene).

Key advantages over simple FTS5:
- Better handling of term frequency saturation
- Document length normalization
- Tunable parameters for domain-specific optimization

Formula: BM25(D, Q) = Σ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D|/avgdl))

Where:
- f(qi, D) = term frequency of qi in document D
- |D| = length of document D
- avgdl = average document length in collection
- k1 = term frequency saturation parameter (1.2-2.0)
- b = length normalization parameter (0.75)
"""

import math
import re
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("jarvis.retrieval")


@dataclass
class Document:
    """A document for BM25 indexing."""

    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tokens: List[str] = field(default_factory=list)
    term_freqs: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if not self.tokens:
            self.tokens = tokenize(self.content)
        if not self.term_freqs:
            self.term_freqs = Counter(self.tokens)


@dataclass
class SearchResult:
    """A search result with BM25 score."""

    doc_id: str
    score: float
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    matched_terms: List[str] = field(default_factory=list)


# Stopwords for English (minimal set for efficiency)
STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "shall", "can", "need", "dare",
    "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "each", "few",
    "more", "most", "other", "some", "such", "no", "nor", "not", "only",
    "own", "same", "so", "than", "too", "very", "just", "and", "but",
    "if", "or", "because", "until", "while", "this", "that", "these",
    "those", "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves", "he", "him", "his",
    "himself", "she", "her", "hers", "herself", "it", "its", "itself",
    "they", "them", "their", "theirs", "themselves", "what", "which",
    "who", "whom", "am", "s", "t", "d", "ll", "ve", "re", "m",
}


def tokenize(text: str, remove_stopwords: bool = True) -> List[str]:
    """
    Tokenize text into terms for BM25 indexing.

    Args:
        text: Input text
        remove_stopwords: Whether to remove common stopwords

    Returns:
        List of lowercase tokens
    """
    if not text:
        return []

    # Lowercase and extract word tokens
    tokens = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())

    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]

    return tokens


class BM25Index:
    """
    BM25 index for fast document retrieval.

    Usage:
        index = BM25Index()
        index.add_document("doc1", "This is a test document")
        index.add_document("doc2", "Another document about testing")
        results = index.search("test document", k=5)
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        delta: float = 0.5,  # BM25+ parameter
    ):
        """
        Initialize BM25 index.

        Args:
            k1: Term frequency saturation parameter (1.2-2.0 recommended)
            b: Length normalization parameter (0.75 is standard)
            delta: BM25+ lower bound parameter
        """
        self.k1 = k1
        self.b = b
        self.delta = delta

        # Index storage
        self.documents: Dict[str, Document] = {}
        self.doc_count = 0
        self.avgdl = 0.0  # Average document length
        self.total_tokens = 0

        # Inverted index: term -> set of doc_ids
        self.inverted_index: Dict[str, set] = {}
        # Document frequency: term -> number of docs containing term
        self.doc_freqs: Dict[str, int] = {}

    def add_document(
        self,
        doc_id: str,
        content: str,
        metadata: Dict[str, Any] = None,
    ) -> None:
        """Add a document to the index."""
        if doc_id in self.documents:
            # Update existing document
            self._remove_from_index(doc_id)

        doc = Document(
            id=doc_id,
            content=content,
            metadata=metadata or {},
        )

        self.documents[doc_id] = doc
        self.doc_count += 1
        self.total_tokens += len(doc.tokens)
        self.avgdl = self.total_tokens / self.doc_count

        # Update inverted index
        for term in set(doc.tokens):
            if term not in self.inverted_index:
                self.inverted_index[term] = set()
                self.doc_freqs[term] = 0
            self.inverted_index[term].add(doc_id)
            self.doc_freqs[term] += 1

    def _remove_from_index(self, doc_id: str) -> None:
        """Remove a document from the index."""
        if doc_id not in self.documents:
            return

        doc = self.documents[doc_id]

        # Update inverted index
        for term in set(doc.tokens):
            if term in self.inverted_index:
                self.inverted_index[term].discard(doc_id)
                self.doc_freqs[term] -= 1
                if self.doc_freqs[term] <= 0:
                    del self.inverted_index[term]
                    del self.doc_freqs[term]

        self.total_tokens -= len(doc.tokens)
        self.doc_count -= 1
        if self.doc_count > 0:
            self.avgdl = self.total_tokens / self.doc_count
        else:
            self.avgdl = 0

        del self.documents[doc_id]

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document by ID."""
        if doc_id in self.documents:
            self._remove_from_index(doc_id)
            return True
        return False

    def _idf(self, term: str) -> float:
        """
        Calculate IDF (Inverse Document Frequency) for a term.

        Uses the Robertson-Sparck Jones IDF formula.
        """
        n = self.doc_freqs.get(term, 0)
        if n == 0:
            return 0.0
        return math.log((self.doc_count - n + 0.5) / (n + 0.5) + 1)

    def _score_document(
        self,
        doc: Document,
        query_terms: List[str],
    ) -> Tuple[float, List[str]]:
        """
        Calculate BM25+ score for a document given query terms.

        Returns (score, matched_terms).
        """
        score = 0.0
        matched_terms = []
        doc_len = len(doc.tokens)

        for term in query_terms:
            if term not in doc.term_freqs:
                continue

            matched_terms.append(term)
            tf = doc.term_freqs[term]
            idf = self._idf(term)

            # BM25+ formula
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1))
            score += idf * (numerator / denominator + self.delta)

        return score, matched_terms

    def search(
        self,
        query: str,
        k: int = 10,
        min_score: float = 0.0,
    ) -> List[SearchResult]:
        """
        Search the index using BM25 ranking.

        Args:
            query: Search query
            k: Maximum number of results
            min_score: Minimum score threshold

        Returns:
            List of SearchResult objects, sorted by score descending
        """
        query_terms = tokenize(query)

        if not query_terms:
            return []

        # Find candidate documents (those containing at least one query term)
        candidate_ids = set()
        for term in query_terms:
            if term in self.inverted_index:
                candidate_ids.update(self.inverted_index[term])

        if not candidate_ids:
            return []

        # Score all candidates
        results = []
        for doc_id in candidate_ids:
            doc = self.documents[doc_id]
            score, matched = self._score_document(doc, query_terms)

            if score >= min_score:
                results.append(
                    SearchResult(
                        doc_id=doc_id,
                        score=score,
                        content=doc.content,
                        metadata=doc.metadata,
                        matched_terms=matched,
                    )
                )

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)

        return results[:k]

    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            "doc_count": self.doc_count,
            "total_tokens": self.total_tokens,
            "avgdl": self.avgdl,
            "unique_terms": len(self.inverted_index),
            "k1": self.k1,
            "b": self.b,
        }


class HybridRetriever:
    """
    Hybrid retriever combining BM25 with FTS5 from SQLite.

    This provides the best of both worlds:
    - BM25 for sophisticated ranking
    - FTS5 for fast initial filtering

    Usage:
        retriever = HybridRetriever(memory_store)
        retriever.build_index()  # Initial build
        results = retriever.search("query", k=10)
    """

    def __init__(self, memory_store: Any):
        self.memory = memory_store
        self.bm25_facts = BM25Index()
        self.bm25_reflections = BM25Index()
        self._built = False

    def build_index(self, force: bool = False) -> Dict[str, int]:
        """
        Build BM25 indexes from memory store.

        Args:
            force: Force rebuild even if already built

        Returns:
            Dict with counts of indexed items
        """
        if self._built and not force:
            return {"facts": len(self.bm25_facts.documents), "reflections": len(self.bm25_reflections.documents)}

        counts = {"facts": 0, "reflections": 0}

        # Index facts
        try:
            cursor = self.memory.conn.execute("SELECT id, entity, fact, confidence FROM facts")
            for row in cursor.fetchall():
                doc_id = f"fact_{row['id']}"
                content = f"{row['entity']}: {row['fact']}"
                self.bm25_facts.add_document(
                    doc_id,
                    content,
                    {"id": row["id"], "entity": row["entity"], "confidence": row["confidence"]},
                )
                counts["facts"] += 1
        except Exception as e:
            logger.warning(f"Error indexing facts: {e}")

        # Index reflections
        try:
            cursor = self.memory.conn.execute(
                "SELECT id, trigger, lesson, new_approach FROM reflections"
            )
            for row in cursor.fetchall():
                doc_id = f"reflection_{row['id']}"
                content = f"{row['trigger']} {row['lesson']} {row['new_approach'] or ''}"
                self.bm25_reflections.add_document(
                    doc_id,
                    content,
                    {"id": row["id"], "trigger": row["trigger"], "lesson": row["lesson"]},
                )
                counts["reflections"] += 1
        except Exception as e:
            logger.warning(f"Error indexing reflections: {e}")

        self._built = True
        logger.info(f"Built BM25 index: {counts}")
        return counts

    def search_facts(
        self,
        query: str,
        k: int = 10,
        min_score: float = 0.5,
    ) -> List[SearchResult]:
        """Search facts using BM25."""
        if not self._built:
            self.build_index()
        return self.bm25_facts.search(query, k=k, min_score=min_score)

    def search_reflections(
        self,
        query: str,
        k: int = 5,
        min_score: float = 0.3,
    ) -> List[SearchResult]:
        """Search reflections using BM25."""
        if not self._built:
            self.build_index()
        return self.bm25_reflections.search(query, k=k, min_score=min_score)

    def search_all(
        self,
        query: str,
        k: int = 10,
    ) -> Dict[str, List[SearchResult]]:
        """
        Search all indexes and return combined results.

        Returns dict with 'facts' and 'reflections' keys.
        """
        return {
            "facts": self.search_facts(query, k=k),
            "reflections": self.search_reflections(query, k=min(k, 5)),
        }

    def add_fact(self, fact_id: int, entity: str, fact_text: str, confidence: float = 0.8):
        """Add a new fact to the BM25 index."""
        doc_id = f"fact_{fact_id}"
        content = f"{entity}: {fact_text}"
        self.bm25_facts.add_document(
            doc_id,
            content,
            {"id": fact_id, "entity": entity, "confidence": confidence},
        )

    def add_reflection(self, reflection_id: int, trigger: str, lesson: str, approach: str = ""):
        """Add a new reflection to the BM25 index."""
        doc_id = f"reflection_{reflection_id}"
        content = f"{trigger} {lesson} {approach}"
        self.bm25_reflections.add_document(
            doc_id,
            content,
            {"id": reflection_id, "trigger": trigger, "lesson": lesson},
        )


# Convenience function for quick search
def bm25_search(
    texts: List[str],
    query: str,
    k: int = 10,
) -> List[Tuple[int, float]]:
    """
    Quick BM25 search over a list of texts.

    Args:
        texts: List of text documents
        query: Search query
        k: Number of results

    Returns:
        List of (index, score) tuples
    """
    index = BM25Index()
    for i, text in enumerate(texts):
        index.add_document(str(i), text)

    results = index.search(query, k=k)
    return [(int(r.doc_id), r.score) for r in results]
