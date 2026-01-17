"""Unit tests for the evidence fusion module."""

import pytest

from evidence.fusion import fuse_candidates_for_question
from schemas.internal.evidence import EvidenceCandidate


def test_fuse_candidates_for_question_basic():
    """Test basic functionality of fuse_candidates_for_question."""
    question_id = "q1"
    
    candidate1 = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="p1",
        title="Title 1",
        page=1,
        text="Text 1",
        source="rule_based",
        score=0.8
    )
    
    candidate2 = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="p2",
        title="Title 2", 
        page=2,
        text="Text 2",
        source="retrieval",
        score=0.7
    )
    
    result = fuse_candidates_for_question(
        question_id,
        candidates_by_engine={
            "rule_based": [candidate1],
            "retrieval": [candidate2]
        }
    )
    
    assert len(result) == 2
    assert result[0].question_id == question_id
    assert result[0].paragraph_id in ["p1", "p2"]
    assert result[0].fusion_score >= 0
    assert result[0].support_count >= 1


def test_fuse_candidates_for_question_empty_engines():
    """Test fusion with empty engine results."""
    question_id = "q1"
    
    result = fuse_candidates_for_question(
        question_id,
        candidates_by_engine={}
    )
    
    assert result == []


def test_fuse_candidates_for_question_different_rrf_k():
    """Test fusion with different RRF k values."""
    question_id = "q1"
    
    candidate1 = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="p1",
        title="Title 1",
        page=1,
        text="Text 1",
        source="rule_based",
        score=0.8
    )
    
    result = fuse_candidates_for_question(
        question_id,
        candidates_by_engine={
            "rule_based": [candidate1]
        },
        rrf_k=100  # Different k value
    )
    
    assert len(result) == 1
    assert result[0].question_id == question_id


def test_fuse_candidates_for_question_with_weights():
    """Test fusion with engine weights."""
    question_id = "q1"
    
    candidate1 = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="p1",
        title="Title 1",
        page=1,
        text="Text 1",
        source="rule_based",
        score=0.8
    )
    
    candidate2 = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="p1",  # Same paragraph for cross-engine scoring
        title="Title 2",
        page=2,
        text="Text 2",
        source="retrieval",
        score=0.7
    )
    
    result = fuse_candidates_for_question(
        question_id,
        candidates_by_engine={
            "rule_based": [candidate1],
            "retrieval": [candidate2]
        },
        engine_weights={"rule_based": 2.0, "retrieval": 1.0}
    )
    
    assert len(result) == 1  # Same paragraph_id should be fused
    assert result[0].support_count == 2  # Both engines support this paragraph
    assert result[0].fusion_score >= 0


def test_fuse_candidates_for_question_invalid_rrf_k():
    """Test fusion with invalid RRF k value raises error."""
    question_id = "q1"
    
    candidate1 = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="p1",
        title="Title 1",
        page=1,
        text="Text 1",
        source="rule_based",
        score=0.8
    )
    
    with pytest.raises(ValueError, match="rrf_k must be >= 1"):
        fuse_candidates_for_question(
            question_id,
            candidates_by_engine={
                "rule_based": [candidate1]
            },
            rrf_k=0  # Invalid k value
        )


def test_fuse_candidates_for_question_invalid_weights():
    """Test fusion with negative engine weights raises error."""
    question_id = "q1"

    candidate1 = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="p1",
        title="Title 1",
        page=1,
        text="Text 1",
        source="rule_based",
        score=0.8
    )

    with pytest.raises(ValueError, match="engine_weights.*must be >= 0"):
        fuse_candidates_for_question(
            question_id,
            candidates_by_engine={
                "rule_based": [candidate1]
            },
            engine_weights={"rule_based": -1.0}  # Negative weight
        )


def test_fuse_candidates_for_question_mismatched_question_id():
    """Test that candidates with mismatched question_id are filtered out."""
    question_id = "q1"
    wrong_question_id = "q2"
    
    candidate_correct = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="p1",
        title="Title 1",
        page=1,
        text="Text 1",
        source="rule_based",
        score=0.8
    )
    
    candidate_wrong = EvidenceCandidate(
        question_id=wrong_question_id,  # Different question ID
        paragraph_id="p2",
        title="Title 2",
        page=2,
        text="Text 2",
        source="retrieval",
        score=0.7
    )
    
    result = fuse_candidates_for_question(
        question_id,
        candidates_by_engine={
            "rule_based": [candidate_correct, candidate_wrong]
        }
    )
    
    # Only the candidate with matching question_id should be included
    assert len(result) == 1
    assert result[0].paragraph_id == "p1"


def test_fuse_candidates_for_question_no_paragraph_id():
    """Test that candidates with no paragraph_id are filtered out."""
    question_id = "q1"
    
    candidate_with_pid = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="p1",
        title="Title 1",
        page=1,
        text="Text 1",
        source="rule_based",
        score=0.8
    )
    
    candidate_no_pid = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="",  # Empty paragraph_id
        title="Title 2",
        page=2,
        text="Text 2",
        source="retrieval",
        score=0.7
    )
    
    result = fuse_candidates_for_question(
        question_id,
        candidates_by_engine={
            "rule_based": [candidate_with_pid, candidate_no_pid]
        }
    )
    
    # Only the candidate with a valid paragraph_id should be included
    assert len(result) == 1
    assert result[0].paragraph_id == "p1"


def test_fuse_candidates_for_question_duplicate_paragraphs():
    """Test fusion handles duplicate paragraphs from multiple engines."""
    question_id = "q1"
    
    candidate1 = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="p1",
        title="Title 1",
        page=1,
        text="Text 1 - Rule Based",
        source="rule_based",
        score=0.8
    )
    
    candidate2 = EvidenceCandidate(
        question_id=question_id,
        paragraph_id="p1",  # Same paragraph ID
        title="Title 1",
        page=1,
        text="Text 1 - Retrieval",
        source="retrieval",
        score=0.9
    )
    
    result = fuse_candidates_for_question(
        question_id,
        candidates_by_engine={
            "rule_based": [candidate1],
            "retrieval": [candidate2]
        }
    )
    
    # Should have only one fused result for the same paragraph
    assert len(result) == 1
    assert result[0].support_count == 2  # Supported by both engines
    assert len(result[0].supports) == 2  # Two support records