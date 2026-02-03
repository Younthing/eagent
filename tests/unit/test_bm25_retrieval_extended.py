"""Unit tests for the BM25 retrieval module."""

from retrieval.engines.bm25 import BM25Index, BM25Hit
from retrieval.tokenization import TokenizerConfig


def test_bm25_index_creation():
    """Test basic BM25 index creation."""
    index = BM25Index(
        term_freqs=[{"test": 1, "document": 1}],
        doc_lengths=[2],
        idf={"test": 1.0, "document": 1.0},
        avgdl=2.0
    )
    
    assert index.size == 1


def test_bm25_index_search_basic():
    """Test basic BM25 search functionality."""
    index = BM25Index(
        term_freqs=[{"test": 1, "document": 1}, {"another": 1, "doc": 1}],
        doc_lengths=[2, 2],
        idf={"test": 1.0, "document": 1.0, "another": 1.0, "doc": 1.0},
        avgdl=2.0
    )
    
    results = index.search("test document", top_n=5)
    
    assert isinstance(results, list)
    assert all(isinstance(hit, BM25Hit) for hit in results)
    assert len(results) <= 5  # Respect top_n limit


def test_bm25_index_search_no_results():
    """Test BM25 search with no matching terms."""
    index = BM25Index(
        term_freqs=[{"test": 1, "document": 1}],
        doc_lengths=[2],
        idf={"test": 1.0, "document": 1.0},
        avgdl=2.0
    )
    
    results = index.search("nonexistent terms", top_n=5)
    
    assert results == []


def test_bm25_index_search_empty_query():
    """Test BM25 search with empty query."""
    index = BM25Index(
        term_freqs=[{"test": 1, "document": 1}],
        doc_lengths=[2],
        idf={"test": 1.0, "document": 1.0},
        avgdl=2.0
    )
    
    results = index.search("", top_n=5)
    
    assert results == []


def test_bm25_hit_attributes():
    """Test BM25Hit attributes."""
    hit = BM25Hit(doc_index=1, score=2.5)
    
    assert hit.doc_index == 1
    assert hit.score == 2.5


def test_bm25_index_search_top_n_limit():
    """Test that search respects the top_n parameter."""
    index = BM25Index(
        term_freqs=[
            {"word1": 1}, {"word2": 1}, {"word3": 1}, 
            {"word4": 1}, {"word5": 1}, {"word6": 1}
        ],
        doc_lengths=[1, 1, 1, 1, 1, 1],
        idf={"word1": 1.0, "word2": 1.0, "word3": 1.0, "word4": 1.0, "word5": 1.0, "word6": 1.0},
        avgdl=1.0
    )
    
    results = index.search("word1 word2 word3 word4 word5 word6", top_n=3)
    
    assert len(results) <= 3


def test_bm25_index_custom_parameters():
    """Test BM25 index with custom parameters."""
    index = BM25Index(
        term_freqs=[{"test": 1}],
        doc_lengths=[1],
        idf={"test": 1.0},
        avgdl=1.0,
        k1=2.0,
        b=0.5,
        tokenizer=TokenizerConfig()
    )
    
    assert index.size == 1
    results = index.search("test", top_n=5)
    assert isinstance(results, list)


def test_bm25_index_size_property():
    """Test that the size property returns the correct count."""
    index = BM25Index(
        term_freqs=[{"a": 1}, {"b": 1}, {"c": 1}],
        doc_lengths=[1, 1, 1],
        idf={"a": 1.0, "b": 1.0, "c": 1.0},
        avgdl=1.0
    )
    
    assert index.size == 3


def test_bm25_index_various_k1_b_values():
    """Test that different k1 and b values work correctly."""
    index = BM25Index(
        term_freqs=[{"test": 1, "document": 1}],
        doc_lengths=[2],
        idf={"test": 1.0, "document": 1.0},
        avgdl=2.0,
        k1=0.5,  # Different k1
        b=0.25    # Different b
    )
    
    results = index.search("test document", top_n=5)
    
    assert isinstance(results, list)


def test_bm25_index_large_documents():
    """Test BM25 index with larger documents."""
    large_term_freqs = [{"word" + str(i): 1 for i in range(100)}]
    large_doc_lengths = [100]
    large_idf = {"word" + str(i): 1.5 for i in range(100)}
    
    index = BM25Index(
        term_freqs=large_term_freqs,
        doc_lengths=large_doc_lengths,
        idf=large_idf,
        avgdl=100.0
    )
    
    results = index.search("word1 word2", top_n=10)
    
    assert isinstance(results, list)
    assert len(results) <= 10


def test_bm25_index_duplicate_terms():
    """Test BM25 index with documents containing duplicate terms."""
    index = BM25Index(
        term_freqs=[{"test": 3, "word": 2}],  # Multiple occurrences
        doc_lengths=[5],  # Total length includes duplicates
        idf={"test": 1.0, "word": 1.0},
        avgdl=5.0
    )
    
    results = index.search("test", top_n=5)
    
    assert isinstance(results, list)


def test_bm25_hit_negative_score():
    """Test BM25Hit with negative score."""
    hit = BM25Hit(doc_index=0, score=-1.0)
    
    assert hit.doc_index == 0
    assert hit.score == -1.0


def test_bm25_index_zero_avgdl():
    """Test BM25 index with zero average document length."""
    index = BM25Index(
        term_freqs=[{"test": 1}],
        doc_lengths=[1],
        idf={"test": 1.0},
        avgdl=0.0  # Zero average document length
    )
    
    results = index.search("test", top_n=5)
    
    assert isinstance(results, list)


def test_bm25_index_single_character_terms():
    """Test BM25 index with single character terms."""
    index = BM25Index(
        term_freqs=[{"a": 1, "b": 1, "c": 1}],
        doc_lengths=[3],
        idf={"a": 1.0, "b": 1.0, "c": 1.0},
        avgdl=3.0
    )
    
    results = index.search("a b", top_n=5)
    
    assert isinstance(results, list)
