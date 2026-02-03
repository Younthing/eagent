"""Unit tests for the retrieval BM25 node module."""

from pipelines.graphs.nodes.locators.retrieval_bm25 import bm25_retrieval_locator_node
from schemas.internal.evidence import EvidenceCandidate
from schemas.internal.rob2 import QuestionSet, Rob2Question


def test_bm25_retrieval_locator_node_basic():
    """Test basic functionality of the BM25 retrieval locator node."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Is there evidence for this claim?",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "This document provides evidence for the claim.",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Introduction",
                    "page": 1,
                    "text": "This document provides evidence for the claim."
                }
            ]
        },
        "query_planner": "deterministic",
        "top_k": 5,
        "per_query_top_n": 10,
        "rrf_k": 60
    }

    result = bm25_retrieval_locator_node(state)

    assert "bm25_candidates" in result
    assert "q1" in result["bm25_candidates"]


def test_bm25_retrieval_locator_node_empty_queries():
    """Test BM25 retrieval locator node with empty queries."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Test question",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "Some content here.",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Content",
                    "page": 1,
                    "text": "Some content here."
                }
            ]
        },
        "query_planner": "deterministic",
        "top_k": 5,
        "per_query_top_n": 10,
        "rrf_k": 60
    }

    result = bm25_retrieval_locator_node(state)

    # Even with empty queries, the node should return a valid structure
    assert "bm25_candidates" in result
    assert "q1" in result["bm25_candidates"]


def test_bm25_retrieval_locator_node_no_documents():
    """Test BM25 retrieval locator node with no documents."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Test question",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "",
            "sections": []  # No documents
        },
        "query_planner": "deterministic",
        "top_k": 5,
        "per_query_top_n": 10,
        "rrf_k": 60
    }

    result = bm25_retrieval_locator_node(state)

    assert "bm25_candidates" in result
    assert "q1" in result["bm25_candidates"]


def test_bm25_retrieval_locator_node_top_k_limit():
    """Test that BM25 retrieval locator respects the top_k parameter."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Test question",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "First content match. Second content match.",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Content 1",
                    "page": 1,
                    "text": "First content match."
                },
                {
                    "paragraph_id": "p2",
                    "title": "Content 2",
                    "page": 2,
                    "text": "Second content match."
                }
            ]
        },
        "query_planner": "deterministic",
        "top_k": 1,  # Limit to 1 result
        "per_query_top_n": 10,
        "rrf_k": 60
    }

    result = bm25_retrieval_locator_node(state)

    assert "bm25_candidates" in result
    candidates = result["bm25_candidates"]["q1"]
    assert len(candidates) <= 1  # Respect top_k limit


def test_bm25_retrieval_locator_node_multiple_questions():
    """Test BM25 retrieval locator node with multiple questions."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="First question",
                options=["Y", "N"],
                order=1
            ),
            Rob2Question(
                question_id="q2",
                rob2_id="q2",
                domain="D1",
                text="Second question",
                options=["Y", "N"],
                order=2
            )
        ]
    )

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "Content relevant to both questions.",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Content",
                    "page": 1,
                    "text": "Content relevant to both questions."
                }
            ]
        },
        "query_planner": "deterministic",
        "top_k": 3,
        "per_query_top_n": 10,
        "rrf_k": 60
    }

    result = bm25_retrieval_locator_node(state)

    assert "bm25_candidates" in result
    assert "q1" in result["bm25_candidates"]
    assert "q2" in result["bm25_candidates"]


def test_bm25_retrieval_locator_node_merges_retry_questions() -> None:
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="First question",
                options=["Y", "N"],
                order=1,
            ),
            Rob2Question(
                question_id="q2",
                rob2_id="q2",
                domain="D1",
                text="Second question",
                options=["Y", "N"],
                order=2,
            ),
        ],
    )

    prev_candidate = EvidenceCandidate(
        question_id="q2",
        paragraph_id="p_prev",
        title="Previous",
        page=9,
        text="Previous evidence.",
        source="retrieval",
        score=1.0,
        engine="bm25",
    )

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "Content for q1.",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Content",
                    "page": 1,
                    "text": "Content for q1.",
                }
            ],
        },
        "query_planner": "deterministic",
        "top_k": 3,
        "per_query_top_n": 10,
        "rrf_k": 60,
        "retry_question_ids": ["q1"],
        "bm25_candidates": {"q2": [prev_candidate.model_dump()]},
        "bm25_queries": {"q2": ["prev query"]},
        "bm25_rankings": {"q2": {"prev query": [{"paragraph_id": "p_prev", "score": 0.1}]}},
        "bm25_evidence": [{"question_id": "q2", "items": [prev_candidate.model_dump()]}],
    }

    result = bm25_retrieval_locator_node(state)

    assert result["bm25_candidates"]["q2"] == [prev_candidate.model_dump()]
    assert result["bm25_queries"]["q2"] == ["prev query"]


def test_bm25_retrieval_locator_node_empty_state():
    """Test BM25 retrieval locator node with minimal state."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Test question",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "",
            "sections": []
        },
        "query_planner": "deterministic",
        "top_k": 5,
        "per_query_top_n": 10,
        "rrf_k": 60
    }

    result = bm25_retrieval_locator_node(state)

    assert "bm25_candidates" in result


def test_bm25_retrieval_locator_node_long_text():
    """Test BM25 retrieval locator node with longer text."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Test question",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    long_text = "This is a very long text with lots of content and repeated words " * 100

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": long_text,
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Long Content",
                    "page": 1,
                    "text": long_text
                }
            ]
        },
        "query_planner": "deterministic",
        "top_k": 5,
        "per_query_top_n": 10,
        "rrf_k": 60
    }

    result = bm25_retrieval_locator_node(state)

    assert "bm25_candidates" in result
    assert "q1" in result["bm25_candidates"]


def test_bm25_retrieval_locator_node_special_characters():
    """Test BM25 retrieval locator node with special characters in text."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Test with symbols?",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "Text with symbols: !@#$%^&*()_+{}[]|\\:;\"'<>?,./",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Special Char Content!",
                    "page": 1,
                    "text": "Text with symbols: !@#$%^&*()_+{}[]|\\:;\"'<>?,./"
                }
            ]
        },
        "query_planner": "deterministic",
        "top_k": 5,
        "per_query_top_n": 10,
        "rrf_k": 60
    }

    result = bm25_retrieval_locator_node(state)

    assert "bm25_candidates" in result
    assert "q1" in result["bm25_candidates"]


def test_bm25_retrieval_locator_node_unicode_text():
    """Test BM25 retrieval locator node with unicode text."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Unicode test",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "Text with unicode: café, naïve, résumé, Москва, 東京",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Unicode Content",
                    "page": 1,
                    "text": "Text with unicode: café, naïve, résumé, Москва, 東京"
                }
            ]
        },
        "query_planner": "deterministic",
        "top_k": 5,
        "per_query_top_n": 10,
        "rrf_k": 60
    }

    result = bm25_retrieval_locator_node(state)

    assert "bm25_candidates" in result
    assert "q1" in result["bm25_candidates"]


def test_bm25_retrieval_locator_node_case_variations():
    """Test BM25 retrieval locator node with case variations."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Case test",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    state = {
        "question_set": question_set.model_dump(),
        "doc_structure": {
            "body": "This Text Has Mixed CASE and VarIED capitalIZATION",
            "sections": [
                {
                    "paragraph_id": "p1",
                    "title": "Mixed Case Content",
                    "page": 1,
                    "text": "This Text Has Mixed CASE and VarIED capitalIZATION"
                }
            ]
        },
        "query_planner": "deterministic",
        "top_k": 5,
        "per_query_top_n": 10,
        "rrf_k": 60
    }

    result = bm25_retrieval_locator_node(state)

    assert "bm25_candidates" in result
    assert "q1" in result["bm25_candidates"]
