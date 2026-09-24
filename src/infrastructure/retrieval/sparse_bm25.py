"""
CampusGrid AI: Pure Python BM25 Sparse Keyword Search Engine
Implements Okapi BM25 algorithm for fast lexical matching over regulatory clauses.
"""

import math
import re
from typing import List, Dict, Any, Tuple
from src.domain.entities.rag import DocumentClause
from src.domain.interfaces.keyword_search import KeywordSearchEngine

class BM25SearchEngine(KeywordSearchEngine):
    """Okapi BM25 inverted index for exact keyword and clause reference matching."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: List[DocumentClause] = []
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0.0
        self.df: Dict[str, int] = {}
        self.doc_freqs: List[Dict[str, int]] = []

    def _tokenize(self, text: str) -> List[str]:
        # Lowercase and split on non-alphanumeric
        tokens = re.findall(r"\b[a-zA-Z0-9_\-\.]+\b", text.lower())
        return tokens

    @property
    def documents(self) -> List[DocumentClause]:
        return list(self.corpus)

    def add_documents(self, documents: List[DocumentClause]):
        """Appends clauses; IDF and average length are recomputed over the whole corpus."""
        self.index_documents(self.corpus + list(documents))

    def index_documents(self, documents: List[DocumentClause]):
        self.corpus = list(documents)
        self.doc_lengths = []
        self.df = {}
        self.doc_freqs = []

        total_tokens = 0
        for doc in documents:
            combined = f"{doc.source_document} {doc.clause_reference} {doc.section_title or ''} {doc.content}"
            tokens = self._tokenize(combined)
            length = len(tokens)
            self.doc_lengths.append(length)
            total_tokens += length

            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self.doc_freqs.append(tf)

            for t in tf.keys():
                self.df[t] = self.df.get(t, 0) + 1

        self.avg_doc_length = (total_tokens / len(documents)) if documents else 1.0

    def search(self, query: str, top_k: int = 5) -> List[Tuple[DocumentClause, float]]:
        if not self.corpus:
            return []

        query_tokens = self._tokenize(query)
        num_docs = len(self.corpus)
        scores: List[Tuple[int, float]] = []

        for idx in range(num_docs):
            doc_len = self.doc_lengths[idx]
            doc_tf = self.doc_freqs[idx]
            score = 0.0

            for q_term in query_tokens:
                if q_term not in doc_tf:
                    continue

                freq = doc_tf[q_term]
                df_term = self.df.get(q_term, 0)
                # IDF calculation with smoothing
                idf = math.log((num_docs - df_term + 0.5) / (df_term + 0.5) + 1.0)
                numerator = freq * (self.k1 + 1.0)
                denominator = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_length))
                score += idf * (numerator / denominator)

            if score > 0.0:
                scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [(self.corpus[idx], score) for idx, score in scores[:top_k]]
