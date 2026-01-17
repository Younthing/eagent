"""Unit tests for the core configuration module."""

import os
from unittest.mock import patch

import pytest
from core.config import Settings, get_settings


def test_settings_defaults():
    """Test that Settings initializes with expected defaults."""
    settings = Settings()
    
    # Check default locator settings
    assert settings.locator_tokenizer == "auto"
    assert settings.locator_char_ngram == 2
    
    # Check default query planner settings
    assert settings.query_planner_temperature == 0.0
    assert settings.query_planner_max_retries == 2
    
    # Check default reranker settings
    assert settings.reranker_max_length == 512
    assert settings.reranker_batch_size == 8
    assert settings.reranker_top_n == 50
    
    # Check default domain audit settings
    assert settings.domain_audit_mode == "none"
    assert settings.domain_audit_patch_window == 0
    assert settings.domain_audit_max_patches_per_question == 3


def test_settings_with_env_vars(monkeypatch):
    """Test that Settings properly loads values from environment variables."""
    monkeypatch.setenv("LOCATOR_CHAR_NGRAM", "3")
    monkeypatch.setenv("QUERY_PLANNER_TEMPERATURE", "0.5")
    monkeypatch.setenv("DOMAIN_AUDIT_MODE", "strict")
    
    settings = Settings()
    
    assert settings.locator_char_ngram == 3
    assert settings.query_planner_temperature == 0.5
    assert settings.domain_audit_mode == "strict"


def test_settings_validation():
    """Test that settings validation works correctly."""
    # Test invalid rrf_k value in evidence fusion function (indirect test)
    from evidence.fusion import fuse_candidates_for_question
    from schemas.internal.evidence import EvidenceCandidate

    with pytest.raises(ValueError, match="rrf_k must be >= 1"):
        fuse_candidates_for_question(
            "test_q",
            candidates_by_engine={},
            rrf_k=0  # Invalid value
        )

    # Create valid EvidenceCandidate with required fields
    valid_candidate = EvidenceCandidate(
        question_id="test_q",
        paragraph_id="p1",
        title="Test",
        page=1,
        text="Test text",
        source="rule_based",  # Valid source
        score=0.5  # Score is required
    )

    with pytest.raises(ValueError, match="engine_weights.*must be >= 0"):
        fuse_candidates_for_question(
            "test_q",
            candidates_by_engine={
                "engine1": [valid_candidate]
            },
            engine_weights={"engine1": -1.0}  # Invalid negative weight
        )


def test_get_settings_singleton():
    """Test that get_settings returns the same instance each time."""
    settings1 = get_settings()
    settings2 = get_settings()
    
    assert settings1 is settings2
    assert isinstance(settings1, Settings)
    assert isinstance(settings2, Settings)


def test_settings_extra_field_handling():
    """Test that settings ignores extra fields."""
    # This should not raise an error despite having unknown fields
    with patch.dict(os.environ, {"UNKNOWN_FIELD": "value"}):
        settings = Settings()
        
    # The settings object should still be valid
    assert hasattr(settings, "locator_tokenizer")


def test_settings_preprocess_defaults():
    """Test preprocess-related settings defaults."""
    settings = Settings()
    
    assert settings.preprocess_drop_references is True