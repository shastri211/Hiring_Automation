"""Tests for ScreenerService._sanitize_context — purely unit, no DB/LLM/network calls."""
import pytest
from app.services.screener import screener_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize(candidate: dict, job: dict) -> dict:
    return screener_service._sanitize_context(candidate, job)


def _job_with(*requirement_keywords) -> dict:
    """Build a minimal job profile whose requirements contain the given keywords."""
    return {"required_capabilities": list(requirement_keywords), "preferred_capabilities": [], "requirements": []}


def _job_empty() -> dict:
    return {"required_capabilities": [], "preferred_capabilities": [], "requirements": []}


# ---------------------------------------------------------------------------
# PII removal — always stripped regardless of job
# ---------------------------------------------------------------------------

class TestPIIRemoval:
    def test_removes_name(self):
        result = _sanitize({"name": "Alice Smith", "skills": ["Python"]}, _job_empty())
        assert "name" not in result
        assert result["skills"] == ["Python"]

    def test_removes_email(self):
        result = _sanitize({"email": "alice@example.com", "experience": 5}, _job_empty())
        assert "email" not in result

    def test_removes_phone(self):
        result = _sanitize({"phone": "+1-555-0000", "skills": []}, _job_empty())
        assert "phone" not in result

    def test_removes_contact(self):
        result = _sanitize({"contact": "linkedin.com/alice", "skills": []}, _job_empty())
        assert "contact" not in result

    def test_removes_hobbies(self):
        result = _sanitize({"hobbies": ["chess", "hiking"], "skills": []}, _job_empty())
        assert "hobbies" not in result

    def test_removes_all_pii_at_once(self):
        candidate = {
            "name": "Bob",
            "email": "bob@x.com",
            "phone": "123",
            "contact": "linkedin",
            "hobbies": ["reading"],
            "skills": ["Java"],
            "experience_years": 3,
        }
        result = _sanitize(candidate, _job_empty())
        for field in ["name", "email", "phone", "contact", "hobbies"]:
            assert field not in result
        assert result["skills"] == ["Java"]
        assert result["experience_years"] == 3

    def test_no_pii_fields_present_is_safe(self):
        candidate = {"skills": ["Go"], "experience_years": 2}
        result = _sanitize(candidate, _job_empty())
        assert result == candidate


# ---------------------------------------------------------------------------
# Languages — conditional on job mentioning "language" or "bilingual"
# ---------------------------------------------------------------------------

class TestLanguagesConditional:
    def test_drops_languages_when_job_has_no_language_requirement(self):
        candidate = {"skills": ["Python"], "languages": ["English", "French"]}
        result = _sanitize(candidate, _job_empty())
        assert "languages" not in result

    def test_keeps_languages_when_job_requires_language(self):
        candidate = {"skills": ["Python"], "languages": ["English", "French"]}
        job = _job_with("language proficiency")
        result = _sanitize(candidate, job)
        assert "languages" in result

    def test_keeps_languages_when_job_requires_bilingual(self):
        candidate = {"skills": ["Python"], "languages": ["English", "Spanish"]}
        job = _job_with("bilingual candidate preferred")
        result = _sanitize(candidate, job)
        assert "languages" in result

    def test_no_languages_field_is_safe(self):
        candidate = {"skills": ["Rust"]}
        result = _sanitize(candidate, _job_empty())
        assert "languages" not in result  # never added
        assert result["skills"] == ["Rust"]


# ---------------------------------------------------------------------------
# Certifications — conditional on job mentioning certif/licen/degree
# ---------------------------------------------------------------------------

class TestCertificationsConditional:
    def test_drops_certifications_when_job_has_no_cert_requirement(self):
        candidate = {"skills": ["SQL"], "certifications": ["AWS Certified Developer"]}
        result = _sanitize(candidate, _job_empty())
        assert "certifications" not in result

    def test_keeps_certifications_when_job_mentions_certif(self):
        candidate = {"skills": ["SQL"], "certifications": ["AWS Certified Developer"]}
        job = _job_with("certifications required")
        result = _sanitize(candidate, job)
        assert "certifications" in result

    def test_keeps_certifications_when_job_mentions_license(self):
        candidate = {"certifications": ["PMP"]}
        job = _job_with("licensed professional")
        result = _sanitize(candidate, job)
        assert "certifications" in result

    def test_keeps_certifications_when_job_mentions_degree(self):
        candidate = {"certifications": ["MBA"]}
        job = _job_with("degree required")
        result = _sanitize(candidate, job)
        assert "certifications" in result

    def test_no_certifications_field_is_safe(self):
        candidate = {"skills": ["Docker"]}
        result = _sanitize(candidate, _job_empty())
        assert "certifications" not in result
        assert result["skills"] == ["Docker"]


# ---------------------------------------------------------------------------
# Non-conditional fields are always preserved
# ---------------------------------------------------------------------------

class TestPreservedFields:
    def test_preserves_skills(self):
        candidate = {"skills": ["Python", "FastAPI"]}
        assert _sanitize(candidate, _job_empty())["skills"] == ["Python", "FastAPI"]

    def test_preserves_experience(self):
        candidate = {"experience": [{"company": "Acme", "role": "SWE"}]}
        result = _sanitize(candidate, _job_empty())
        assert "experience" in result

    def test_preserves_education(self):
        candidate = {"education": [{"degree": "BSc Computer Science"}]}
        result = _sanitize(candidate, _job_empty())
        assert "education" in result

    def test_preserves_summary(self):
        candidate = {"summary": "Experienced backend engineer"}
        result = _sanitize(candidate, _job_empty())
        assert result["summary"] == "Experienced backend engineer"

    def test_does_not_mutate_original_candidate(self):
        candidate = {"name": "Alice", "skills": ["Python"]}
        original_keys = set(candidate.keys())
        _sanitize(candidate, _job_empty())
        assert set(candidate.keys()) == original_keys  # original unchanged


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_candidate_profile(self):
        result = _sanitize({}, _job_empty())
        assert result == {}

    def test_empty_job_profile(self):
        candidate = {"name": "X", "skills": ["Rust"], "languages": ["DE"], "certifications": ["AWS"]}
        result = _sanitize(candidate, {})
        assert "name" not in result
        assert "languages" not in result
        assert "certifications" not in result
        assert result["skills"] == ["Rust"]

    def test_job_profile_with_no_capabilities_keys(self):
        candidate = {"name": "Y", "languages": ["FR"]}
        result = _sanitize(candidate, {"title": "Developer"})
        assert "name" not in result
        assert "languages" not in result

    def test_certifications_kept_when_aws_in_requirements(self):
        # "aws" is a trigger keyword in the first certifications check block
        candidate = {"certifications": ["AWS Solutions Architect"]}
        job = _job_with("AWS experience")
        result = _sanitize(candidate, job)
        assert "certifications" in result
