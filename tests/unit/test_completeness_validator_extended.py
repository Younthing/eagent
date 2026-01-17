"""Unit tests for the completeness validator module."""

import pytest
from evidence.validators.completeness import compute_completeness, CompletenessValidatorConfig
from schemas.internal.evidence import FusedEvidenceCandidate
from schemas.internal.rob2 import QuestionSet, Rob2Question


def test_compute_completeness_basic():
    """Test basic completeness computation functionality."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Is there sufficient evidence?",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    # Create valid candidates
    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="Complete evidence text that addresses the question.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    candidates_by_q = {"q1": [candidate]}

    result = compute_completeness(question_set, candidates_by_q, config=CompletenessValidatorConfig(enforce=True))

    passed, items, failed = result
    assert isinstance(passed, bool)
    assert isinstance(items, list)
    assert isinstance(failed, list)


def test_compute_completeness_with_enforce_false():
    """Test completeness computation with enforce=False."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Is there sufficient evidence?",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="Complete evidence text that addresses the question.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    candidates_by_q = {"q1": [candidate]}

    result = compute_completeness(question_set, candidates_by_q, config=CompletenessValidatorConfig(enforce=False))

    passed, items, failed = result
    # With enforce=False and no required IDs set, it should pass
    assert passed is True


def test_compute_completeness_with_required_questions():
    """Test completeness computation with explicit required question IDs."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Is there sufficient evidence?",
                options=["Y", "N"],
                order=1
            ),
            Rob2Question(
                question_id="q2",
                rob2_id="q2",
                domain="D1",  # Use D1 to avoid needing effect_type
                text="Another question?",
                options=["Y", "N"],
                order=2
            )
        ]
    )

    # Only provide candidates for q1, none for q2
    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="Complete evidence text that addresses the question.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    candidates_by_q = {"q1": [candidate]}  # Missing candidates for q2

    # Specify that both questions are required
    config = CompletenessValidatorConfig(enforce=True, required_question_ids={"q1", "q2"})
    result = compute_completeness(question_set, candidates_by_q, config=config)

    passed, items, failed = result

    # Should fail because q2 is required but has no candidates
    assert passed is False
    assert "q2" in failed


def test_compute_completeness_with_min_passed_requirement():
    """Test completeness computation with minimum passed requirement."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Is there sufficient evidence?",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    # Create one candidate
    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="Complete evidence text that addresses the question.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    candidates_by_q = {"q1": [candidate]}

    # Require at least 1 passed candidate
    config = CompletenessValidatorConfig(enforce=True, min_passed_per_question=1)
    result = compute_completeness(question_set, candidates_by_q, config=config)

    passed, items, failed = result
    assert passed is True  # Has 1 candidate which meets the 1 required

    # Try with higher requirement
    config2 = CompletenessValidatorConfig(enforce=True, min_passed_per_question=2)
    result2 = compute_completeness(question_set, candidates_by_q, config=config2)

    passed2, items2, failed2 = result2
    assert passed2 is False  # Only has 1 candidate but requires 2


def test_compute_completeness_multiple_candidates_same_question():
    """Test completeness computation with multiple candidates for same question."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Is there sufficient evidence?",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    # Create multiple candidates for the same question
    candidate1 = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title 1",
        page=1,
        text="Complete evidence text 1.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    candidate2 = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p2",
        title="Sample Title 2",
        page=2,
        text="Complete evidence text 2.",
        fusion_score=0.7,
        fusion_rank=2,
        support_count=1,
        supports=[]
    )

    candidates_by_q = {"q1": [candidate1, candidate2]}

    config = CompletenessValidatorConfig(enforce=True, min_passed_per_question=1)
    result = compute_completeness(question_set, candidates_by_q, config=config)

    passed, items, failed = result
    assert passed is True


def test_compute_completeness_empty_candidates():
    """Test completeness computation with empty candidates."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Is there sufficient evidence?",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    candidates_by_q = {}  # No candidates for any question

    config = CompletenessValidatorConfig(enforce=True, required_question_ids={"q1"})
    result = compute_completeness(question_set, candidates_by_q, config=config)

    passed, items, failed = result
    assert passed is False
    assert items  # Should still have completeness items for each question
    assert "q1" in failed


def test_compute_completeness_config_validation():
    """Test completeness computation config validation."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Is there sufficient evidence?",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="Complete evidence text that addresses the question.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    candidates_by_q = {"q1": [candidate]}

    # Test with invalid min_passed_per_question
    config = CompletenessValidatorConfig(enforce=True, min_passed_per_question=0)  # Invalid
    with pytest.raises(ValueError, match="min_passed_per_question must be >= 1"):
        compute_completeness(question_set, candidates_by_q, config=config)


def test_compute_completeness_items_structure():
    """Test that completeness items have the correct structure."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Is there sufficient evidence?",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="Complete evidence text that addresses the question.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    candidates_by_q = {"q1": [candidate]}

    result = compute_completeness(question_set, candidates_by_q, config=CompletenessValidatorConfig(enforce=True))

    passed, items, failed = result

    assert len(items) == 1  # One item per question
    item = items[0]

    # Verify the structure of completeness items
    assert hasattr(item, 'question_id')
    assert hasattr(item, 'required')
    assert hasattr(item, 'passed_count')
    assert hasattr(item, 'status')
    assert item.question_id == "q1"
    assert item.passed_count == 1
    assert item.status in ["satisfied", "missing"]


def test_compute_completeness_no_required_questions():
    """Test completeness computation when no questions are marked as required."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1",
                rob2_id="q1",
                domain="D1",
                text="Is there sufficient evidence?",
                options=["Y", "N"],
                order=1
            )
        ]
    )

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="Complete evidence text that addresses the question.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    candidates_by_q = {"q1": [candidate]}

    # With enforce=False and no required_question_ids, should pass regardless
    config = CompletenessValidatorConfig(enforce=False, required_question_ids=None)
    result = compute_completeness(question_set, candidates_by_q, config=config)

    passed, items, failed = result
    assert passed is True


def test_compute_completeness_boundary_conditions():
    """Test completeness computation under boundary conditions."""
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q_test",
                rob2_id="q_test",
                domain="D1",  # Valid domain
                text="Test question",
                options=["Y", "N"],  # Valid options
                order=1
            )
        ]
    )

    candidate = FusedEvidenceCandidate(
        question_id="q_test",
        paragraph_id="p_test",
        title="Test Title",
        page=1,
        text="Test text",
        fusion_score=0.5,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    candidates_by_q = {"q_test": [candidate]}

    result = compute_completeness(question_set, candidates_by_q, config=CompletenessValidatorConfig(enforce=True))

    passed, items, failed = result
    # Should handle the test case appropriately
    assert isinstance(passed, bool)
    assert isinstance(items, list)
    assert isinstance(failed, list)