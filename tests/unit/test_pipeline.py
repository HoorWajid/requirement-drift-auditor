"""
Functional/unit tests for the ML pipeline — run AFTER security tests pass.
"""
import pytest
from app.drift_detector import analyze_pair


@pytest.mark.unit
def test_identical_requirements_are_stable():
    result = analyze_pair(
        "The system must respond within 2 seconds.",
        "The system must respond within 2 seconds."
    )
    assert result["severity"] == "STABLE"
    assert result["cosine_similarity"] > 0.95


@pytest.mark.unit
def test_large_numeric_change_flagged():
    result = analyze_pair(
        "Users must upload files up to 10 MB.",
        "Users can upload files up to 100 MB."
    )
    assert result["severity"] in ("MEDIUM_DRIFT", "CONFLICT")


@pytest.mark.unit
def test_negation_flagged_as_contradiction():
    result = analyze_pair(
        "The system must log all access attempts.",
        "The system must not log any access attempts."
    )
    assert result["nli_label"] == "contradiction"
