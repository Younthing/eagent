"""Unit tests for the existence validator module."""

from evidence.validators.existence import annotate_existence, ExistenceValidatorConfig
from schemas.internal.evidence import FusedEvidenceCandidate
from schemas.internal.documents import DocStructure, SectionSpan


def test_annotate_existence_basic_validation():
    """Test basic existence validation functionality."""
    # Create document structure with a section
    section_span = SectionSpan(
        paragraph_id="p1",  # Use paragraph_id directly in SectionSpan
        title="Sample Section",
        text="This is a sample paragraph text."
    )

    doc_structure = DocStructure(body="This is a sample paragraph text.", sections=[section_span])

    # Create a candidate that should exist
    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="This is a sample paragraph text.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    result = annotate_existence(doc_structure, [candidate], config=ExistenceValidatorConfig())

    assert len(result) == 1
    assert result[0].question_id == "q1"
    assert result[0].paragraph_id == "p1"
    # The result should have an existence verdict
    assert result[0].existence is not None
    assert result[0].existence.label == "pass"


def test_annotate_existence_missing_paragraph():
    """Test existence validation with missing paragraph."""
    # Create document structure without the referenced paragraph
    section_span = SectionSpan(
        paragraph_id="p2",  # Different ID
        title="Sample Section",
        text="This is different paragraph text."
    )

    doc_structure = DocStructure(body="This is different paragraph text.", sections=[section_span])

    # Create a candidate with a paragraph that doesn't exist
    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",  # This paragraph doesn't exist in the structure
        title="Sample Title",
        page=1,
        text="This paragraph does not exist in the document.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    result = annotate_existence(doc_structure, [candidate], config=ExistenceValidatorConfig())

    assert len(result) == 1
    # The result should have a failed existence verdict
    assert result[0].existence is not None
    assert result[0].existence.label == "fail"
    assert result[0].existence.reason == "paragraph_id_not_found"


def test_annotate_existence_text_mismatch():
    """Test existence validation with text mismatch."""
    # Create document structure with a different text
    section_span = SectionSpan(
        paragraph_id="p1",
        title="Sample Section",
        text="Original document text here."
    )

    doc_structure = DocStructure(body="Original document text here.", sections=[section_span])

    # Create a candidate with mismatched text
    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="Completely different candidate text.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    result = annotate_existence(doc_structure, [candidate], config=ExistenceValidatorConfig(require_text_match=True))

    assert len(result) == 1
    # The result should have a failed existence verdict due to text mismatch
    assert result[0].existence is not None
    assert result[0].existence.label == "fail"
    assert result[0].existence.reason == "text_mismatch"


def test_annotate_existence_multiple_candidates():
    """Test existence validation with multiple candidates."""
    # Create document structure with multiple sections
    section1 = SectionSpan(
        paragraph_id="p1",
        title="Section 1",
        text="First paragraph text."
    )

    section2 = SectionSpan(
        paragraph_id="p2",
        title="Section 2",
        text="Second paragraph text."
    )

    doc_structure = DocStructure(body="First paragraph text. Second paragraph text.", sections=[section1, section2])

    # Create candidates
    candidate1 = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Title 1",
        page=1,
        text="First paragraph text.",
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
        text="Second paragraph text.",
        fusion_score=0.8,
        fusion_rank=2,
        support_count=1,
        supports=[]
    )

    result = annotate_existence(doc_structure, [candidate1, candidate2], config=ExistenceValidatorConfig())

    assert len(result) == 2
    # Both should pass as they exist in the document
    assert all(c.existence and c.existence.label == "pass" for c in result)


def test_annotate_existence_empty_inputs():
    """Test existence validation with empty inputs."""
    doc_structure = DocStructure(body="", sections=[])

    result = annotate_existence(doc_structure, [], config=ExistenceValidatorConfig())

    assert result == []


def test_annotate_existence_config_variation():
    """Test existence validation with different config settings."""
    # Create document structure with text that doesn't match exactly
    section_span = SectionSpan(
        paragraph_id="p1",
        title="Sample Section",
        text="Original document text here."
    )

    doc_structure = DocStructure(body="Original document text here.", sections=[section_span])

    # Create a candidate with text that is a substring of the original
    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="document text",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    # With require_text_match=False, this should pass even with incomplete match
    result = annotate_existence(doc_structure, [candidate], config=ExistenceValidatorConfig(require_text_match=False))

    assert len(result) == 1
    # Should pass because we're not checking text match
    assert result[0].existence is not None
    assert result[0].existence.label == "pass"


def test_annotate_existence_preserve_candidate_fields():
    """Test that existence validation preserves other candidate fields."""
    section_span = SectionSpan(
        paragraph_id="p1",
        title="Sample Section",
        text="This is a sample paragraph text."
    )

    doc_structure = DocStructure(body="This is a sample paragraph text.", sections=[section_span])

    original_candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Original Title",
        page=5,
        text="This is a sample paragraph text.",
        fusion_score=0.85,
        fusion_rank=1,
        support_count=2,
        supports=[]  # Will be empty initially
    )

    result = annotate_existence(doc_structure, [original_candidate], config=ExistenceValidatorConfig())

    assert len(result) == 1
    updated_candidate = result[0]

    # Check that non-existence fields are preserved
    assert updated_candidate.question_id == original_candidate.question_id
    assert updated_candidate.paragraph_id == original_candidate.paragraph_id
    assert updated_candidate.title == original_candidate.title
    assert updated_candidate.page == original_candidate.page
    assert updated_candidate.text == original_candidate.text
    assert updated_candidate.fusion_score == original_candidate.fusion_score
    assert updated_candidate.fusion_rank == original_candidate.fusion_rank
    assert updated_candidate.support_count == original_candidate.support_count
    # Existence should be added/updated
    assert updated_candidate.existence is not None


def test_annotate_existence_quote_validation():
    """Test existence validation with quote requirements."""
    section_span = SectionSpan(
        paragraph_id="p1",
        title="Sample Section",
        text="This is a paragraph with specific text."
    )

    doc_structure = DocStructure(body="This is a paragraph with specific text.", sections=[section_span])

    # Create candidate with relevance that has a supporting quote
    from schemas.internal.evidence import RelevanceVerdict

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="This is a paragraph with specific text.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[],
        relevance=RelevanceVerdict(label="relevant", confidence=0.9, supporting_quote="specific text")  # Quote exists in text
    )

    result = annotate_existence(doc_structure, [candidate], config=ExistenceValidatorConfig(require_quote_in_source=True))

    assert len(result) == 1
    # Should pass because the quote exists in the source text
    assert result[0].existence is not None
    assert result[0].existence.label == "pass"
    assert result[0].existence.quote_found is True  # Quote found in source


def test_annotate_existence_quote_not_found():
    """Test existence validation with missing quote."""
    section_span = SectionSpan(
        paragraph_id="p1",
        title="Sample Section",
        text="This is a paragraph with specific text."
    )

    doc_structure = DocStructure(body="This is a paragraph with specific text.", sections=[section_span])

    # Create candidate with relevance that has a quote NOT in the text
    from schemas.internal.evidence import RelevanceVerdict

    candidate = FusedEvidenceCandidate(
        question_id="q1",
        paragraph_id="p1",
        title="Sample Title",
        page=1,
        text="This is a paragraph with specific text.",
        fusion_score=0.8,
        fusion_rank=1,
        support_count=1,
        supports=[],
        relevance=RelevanceVerdict(label="relevant", confidence=0.9, supporting_quote="nonexistent quote")  # Quote doesn't exist in text
    )

    result = annotate_existence(doc_structure, [candidate], config=ExistenceValidatorConfig(require_quote_in_source=True))

    assert len(result) == 1
    # Should fail because the quote doesn't exist in the source text
    assert result[0].existence is not None
    assert result[0].existence.label == "fail"
    assert result[0].existence.reason == "quote_not_found"


def test_annotate_existence_boundary_conditions():
    """Test existence validation under boundary conditions."""
    section_span = SectionSpan(
        paragraph_id="",
        title="",
        text=""  # Empty values
    )

    doc_structure = DocStructure(body="", sections=[section_span])

    candidate = FusedEvidenceCandidate(
        question_id="q_edge",
        paragraph_id="",  # Empty paragraph ID
        title="",
        page=0,
        text="",
        fusion_score=0.0,
        fusion_rank=1,
        support_count=1,
        supports=[]
    )

    result = annotate_existence(doc_structure, [candidate], config=ExistenceValidatorConfig())

    assert len(result) == 1
    # Should handle empty/edge case values appropriately
