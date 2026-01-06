"""Local BM25 retrieval engine (Milestone 4)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from schemas.internal.documents import SectionSpan
from retrieval.tokenization import TokenizerConfig, tokenize_text


@dataclass(frozen=True)
class BM25Hit:
    doc_index: int
    score: float


class BM25Index:
    """A lightweight BM25 index over paragraph spans."""

    def __init__(
        self,
        *,
        term_freqs: List[Dict[str, int]],
        doc_lengths: List[int],
        idf: Dict[str, float],
        avgdl: float,
        k1: float = 1.5,
        b: float = 0.75,
        tokenizer: TokenizerConfig | None = None,
    ) -> None:
        self._term_freqs = term_freqs
        self._doc_lengths = doc_lengths
        self._idf = idf
        self._avgdl = avgdl
        self._k1 = k1
        self._b = b
        self._tokenizer = tokenizer or TokenizerConfig()

    @property
    def size(self) -> int:
        return len(self._term_freqs)

    def search(self, query: str, *, top_n: int = 50) -> List[BM25Hit]:
        """Return top_n BM25 hits for the query."""
        tokens = tokenize_text(query, config=self._tokenizer)
        if not tokens:
            return []

        unique_terms = list(dict.fromkeys(tokens))
        scores: List[BM25Hit] = []

        for doc_index, tf in enumerate(self._term_freqs):
            score = _bm25_score(
                tf=tf,
                doc_len=self._doc_lengths[doc_index],
                avgdl=self._avgdl,
                idf=self._idf,
                terms=unique_terms,
                k1=self._k1,
                b=self._b,
            )
            if score <= 0:
                continue
            scores.append(BM25Hit(doc_index=doc_index, score=score))

        scores.sort(key=lambda hit: (-hit.score, hit.doc_index))
        return scores[:top_n]


def build_bm25_index(
    spans: Sequence[SectionSpan],
    *,
    k1: float = 1.5,
    b: float = 0.75,
    tokenizer: TokenizerConfig | None = None,
) -> BM25Index:
    """Build a BM25 index over spans."""
    term_freqs: List[Dict[str, int]] = []
    doc_lengths: List[int] = []
    doc_freq: Dict[str, int] = {}

    for span in spans:
        tokens = tokenize_text(span.text, config=tokenizer)
        tf: Dict[str, int] = {}
        seen: set[str] = set()
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
            if token not in seen:
                seen.add(token)
                doc_freq[token] = doc_freq.get(token, 0) + 1
        term_freqs.append(tf)
        doc_lengths.append(len(tokens))

    n_docs = max(len(spans), 1)
    avgdl = sum(doc_lengths) / n_docs if doc_lengths else 0.0
    idf = {term: _idf(n_docs, df) for term, df in doc_freq.items()}

    return BM25Index(
        term_freqs=term_freqs,
        doc_lengths=doc_lengths,
        idf=idf,
        avgdl=avgdl,
        k1=k1,
        b=b,
        tokenizer=tokenizer,
    )


def tokenize(text: str) -> List[str]:
    """Tokenize text for BM25 with default configuration."""
    return tokenize_text(text)


def _idf(n_docs: int, df: int) -> float:
    # Standard BM25 idf with +1 inside log for non-negative scores.
    return math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)


def _bm25_score(
    *,
    tf: Dict[str, int],
    doc_len: int,
    avgdl: float,
    idf: Dict[str, float],
    terms: Iterable[str],
    k1: float,
    b: float,
) -> float:
    score = 0.0
    denom_norm = k1 * (1.0 - b + b * (doc_len / avgdl)) if avgdl > 0 else k1
    for term in terms:
        f = tf.get(term, 0)
        if f <= 0:
            continue
        term_idf = idf.get(term)
        if term_idf is None:
            continue
        numerator = f * (k1 + 1.0)
        denominator = f + denom_norm
        score += term_idf * (numerator / denominator)
    return score


__all__ = ["BM25Hit", "BM25Index", "build_bm25_index", "tokenize"]
