"""Unit tests for the relevance validator module."""

import pytest
from evidence.validators.relevance import annotate_relevance, RelevanceValidationConfig
from schemas.internal.evidence import FusedEvidenceCandidate


def test_annotate_relevance_basic():
    """Test basic relevance annotation functionality."""
    question_text = "What is the main finding of this study?"

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="This study found that the intervention had significant positive effects.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    # Test with no LLM (should return unknown relevance)
    result = annotate_relevance(question_text, [candidate], config=RelevanceValidationConfig())

    assert len(result) == 1
    assert result[0].question_id == "q1"
    assert result[0].paragraph_id == "p1"
    # Since no LLM is provided, relevance should be unknown
    assert result[0].relevance is not None
    assert result[0].relevance.label == "unknown"


def test_annotate_relevance_config_validation():
    """Test relevance annotation config validation."""
    question_text = "Test question"

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="This is some text.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    # Test with invalid confidence range
    with pytest.raises(ValueError):
        config = RelevanceValidationConfig(min_confidence=1.5)  # Out of range
        annotate_relevance(question_text, [candidate], config=config)


def test_annotate_relevance_multiple_candidates():
    """Test relevance annotation with multiple candidates."""
    question_text = "What is the main finding of this study?"

    candidate1 = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Title 1",
        page=1,
        text="This study found that the intervention had significant positive effects.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    candidate2 = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p2",
        title="Title 2",
        page=2,
        text="Additional information about the methodology was also provided.",
        fusion_score=0.7,
        fusion_rank=2,
        support_count=1,
        supports=[]
    )

    result = annotate_relevance(question_text, [candidate1, candidate2], config=RelevanceValidationConfig())

    assert len(result) == 2
    # Both should have relevance annotations (even if unknown due to lack of LLM)


def test_annotate_relevance_min_confidence_setting():
    """Test relevance annotation with different min_confidence settings."""
    question_text = "Test question"

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="This is some text.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    # Test with low min confidence
    config_low = RelevanceValidationConfig(min_confidence=0.1)
    result_low = annotate_relevance(question_text, [candidate], config=config_low)

    # Test with high min confidence
    config_high = RelevanceValidationConfig(min_confidence=0.9)
    result_high = annotate_relevance(question_text, [candidate], config=config_high)

    # Both should have results without error
    assert len(result_low) == 1
    assert len(result_high) == 1


def test_annotate_relevance_require_quote_behavior():
    """Test relevance annotation with require_quote flag."""
    question_text = "What is the specific quote about the outcome?"

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="The results showed a significant improvement (p<0.05).",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    # Test with require_supporting_quote=True
    config = RelevanceValidationConfig(require_supporting_quote=True, min_confidence=0.5)
    result = annotate_relevance(question_text, [candidate], config=config)

    assert len(result) == 1
    # Without LLM, relevance is unknown, so the quote requirement doesn't affect the result


def test_annotate_relevance_empty_candidates():
    """Test relevance annotation with empty candidates list."""
    question_text = "Test question"

    result = annotate_relevance(question_text, [], config=RelevanceValidationConfig())

    assert result == []


def test_annotate_relevance_preserve_fields():
    """Test that relevance annotation preserves other fields."""
    question_text = "Test question"

    original_candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Original Title",
        page=5,
        text="Original text content.",
        fusion_score=0.85,
        fusion_rank=1,
        support_count=2,
        supports=[]
    )

    result = annotate_relevance(question_text, [original_candidate], config=RelevanceValidationConfig())

    assert len(result) == 1
    updated_candidate = result[0]

    # Check that non-relevance fields are preserved
    assert updated_candidate.question_id == original_candidate.question_id
    assert updated_candidate.paragraph_id == original_candidate.paragraph_id
    assert updated_candidate.title == original_candidate.title
    assert updated_candidate.page == original_candidate.page
    assert updated_candidate.text == original_candidate.text
    assert updated_candidate.fusion_score == original_candidate.fusion_score
    assert updated_candidate.fusion_rank == original_candidate.fusion_rank
    assert updated_candidate.support_count == original_candidate.support_count
    # Relevance should be added
    assert updated_candidate.relevance is not None


def test_annotate_relevance_boundary_conditions():
    """Test relevance annotation under boundary conditions."""
    question_text = ""  # Empty question

    candidate = FusedEvidenceCandidate(
        question_id="q_edge",
        paragraph_id="",
        title="",
        page=0,
        text="",  # Empty text
        fusion_score=0.0,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    result = annotate_relevance(question_text, [candidate], config=RelevanceValidationConfig())

    assert len(result) == 1
    # Should handle empty/edge case values appropriately


def test_annotate_relevance_config_edge_cases():
    """Test relevance annotation with config edge cases."""
    question_text = "Test question"

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="This is some text.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    # Test with minimum confidence
    config_min = RelevanceValidationConfig(min_confidence=0.0)
    result_min = annotate_relevance(question_text, [candidate], config=config_min)

    assert len(result_min) == 1

    # Test with maximum confidence
    config_max = RelevanceValidationConfig(min_confidence=1.0)
    result_max = annotate_relevance(question_text, [candidate], config=config_max)

    assert len(result_max) == 1


def test_annotate_relevance_special_characters():
    """Test relevance annotation with special characters in text."""
    question_text = "What's the result with special chars? $#@"

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Title with chars: !@#$%",
        page=1,
        text="Text with special chars: £¥©®",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    result = annotate_relevance(question_text, [candidate], config=RelevanceValidationConfig())

    assert len(result) == 1
    # Should handle special characters without issues