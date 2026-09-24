"""
CampusGrid AI: Pure Python BM25 Sparse Keyword Search Engine
Implements Okapi BM25 algorithm for fast lexical matching over regulatory clauses.

Thread-safe: an index is built completely off to the side and then swapped in with a single
assignment, so a search running during an ingestion always sees one consistent index.
"""

import math
import re
import threading
from typing import List, Dict, NamedTuple, Tuple
from src.domain.entities.rag import DocumentClause
from src.domain.interfaces.keyword_search import KeywordSearchEngine


class _Index(NamedTuple):
    corpus: Tuple[DocumentClause, ...]
    doc_lengths: Tuple[int, ...]
    avg_doc_length: float
    df: Dict[str, int]
    doc_freqs: Tuple[Dict[str, int], ...]


_EMPTY = _Index((), (), 1.0, {}, ())


class BM25SearchEngine(KeywordSearchEngine):
    """Okapi BM25 inverted index for exact keyword and clause reference matching."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._index: _Index = _EMPTY
        self._write_lock = threading.Lock()

    def _tokenize(self, text: str) -> List[str]:
        # Lowercase and split on non-alphanumeric
        return re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())

    @property
    def documents(self) -> List[DocumentClause]:
        return list(self._index.corpus)

    def _build(self, documents: List[DocumentClause]) -> _Index:
        doc_lengths, doc_freqs, df = [], [], {}
        total_tokens = 0
        for doc in documents:
            tokens = self._tokenize(f"{doc.source_document} {doc.clause_reference} {doc.section_title or ''} {doc.content}")
            doc_lengths.append(len(tokens))
            total_tokens += len(tokens)
            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            doc_freqs.append(tf)
            for t in tf:
                df[t] = df.get(t, 0) + 1
        avg = (total_tokens / len(documents)) if documents else 1.0
        return _Index(tuple(documents), tuple(doc_lengths), avg, df, tuple(doc_freqs))

    def index_documents(self, documents: List[DocumentClause]):
        with self._write_lock:
            self._index = self._build(list(documents))

    def add_documents(self, documents: List[DocumentClause]):
        """Appends clauses; IDF and average length are recomputed over the whole corpus."""
        with self._write_lock:
            self._index = self._build(list(self._index.corpus) + list(documents))

    def search(self, query: str, top_k: int = 5) -> List[Tuple[DocumentClause, float]]:
        index = self._index  # one consistent snapshot for the whole search
        if not index.corpus:
            return []

        query_tokens = self._tokenize(query)
        num_docs = len(index.corpus)
        scores: List[Tuple[int, float]] = []

        for idx in range(num_docs):
            doc_len = index.doc_lengths[idx]
            doc_tf = index.doc_freqs[idx]
            score = 0.0
            for q_term in query_tokens:
                freq = doc_tf.get(q_term)
                if not freq:
                    continue
                df_term = index.df.get(q_term, 0)
                # IDF calculation with smoothing
                idf = math.log((num_docs - df_term + 0.5) / (df_term + 0.5) + 1.0)
                numerator = freq * (self.k1 + 1.0)
                denominator = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / index.avg_doc_length))
                score += idf * (numerator / denominator)
            if score > 0.0:
                scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [(index.corpus[idx], score) for idx, score in scores[:top_k]]
