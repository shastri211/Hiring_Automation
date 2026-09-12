"""
Focused unit tests for the targeted pipeline correctness fixes.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# --- 1. Error class hierarchy ---

def test_error_class_hierarchy():
    from app.services.llm_provider import (
        LLMError, LLMExhaustionError, InvalidEvaluationResultError,
        RateLimitError, ConfigurationError,
    )
    assert issubclass(LLMExhaustionError, LLMError)
    assert issubclass(InvalidEvaluationResultError, LLMError)
    assert issubclass(RateLimitError, LLMError)
    assert not issubclass(ConfigurationError, LLMError)


# --- 2. _strip_fenced_json ---

def test_strip_plain():
    from app.services.llm_provider import _strip_fenced_json
    raw = '{"score": 75}'
    assert _strip_fenced_json(raw) == raw

def test_strip_fenced_lowercase():
    from app.services.llm_provider import _strip_fenced_json
    raw = "```json\n" + '{"score": 75}' + f"\n```"
    assert json.loads(_strip_fenced_json(raw)) == {"score": 75}

def test_strip_fenced_uppercase():
    from app.services.llm_provider import _strip_fenced_json
    raw = "```JSON\n" + '{"score": 75}' + f"\n```"
    assert json.loads(_strip_fenced_json(raw)) == {"score": 75}

def test_strip_fenced_no_lang():
    from app.services.llm_provider import _strip_fenced_json
    raw = "```\n" + '{"score": 75}' + f"\n```"
    assert json.loads(_strip_fenced_json(raw)) == {"score": 75}

def test_strip_fenced_with_whitespace():
    from app.services.llm_provider import _strip_fenced_json
    raw = "  ```json\n" + '{"score": 0}' + f"\n```  "
    assert json.loads(_strip_fenced_json(raw)) == {"score": 0}


# --- 3. generate_with_fallback raises LLMExhaustionError when all fail ---

def test_exhaustion_all_fail():
    from app.services.llm_provider import LLMProviderFactory, LLMExhaustionError, LLMError
    from app.services.model_registry import model_registry, LLMModelConfig
    fake = [LLMModelConfig("groq", "m-a", 0, ["json"])]
    with patch.object(model_registry, "get_eligible_llm_models", return_value=fake):
        with patch.object(LLMProviderFactory, "get_provider") as gp:
            gp.return_value = MagicMock(generate_json=AsyncMock(side_effect=LLMError("down")))
            with pytest.raises(LLMExhaustionError):
                run(LLMProviderFactory.generate_with_fallback("p", {}))


def test_exhaustion_no_eligible():
    from app.services.llm_provider import LLMProviderFactory, LLMExhaustionError
    from app.services.model_registry import model_registry
    with patch.object(model_registry, "get_eligible_llm_models", return_value=[]):
        with pytest.raises(LLMExhaustionError):
            run(LLMProviderFactory.generate_with_fallback("p", {}))


# --- 4. Successful call returns result ---

def test_generate_success():
    from app.services.llm_provider import LLMProviderFactory
    from app.services.model_registry import model_registry, LLMModelConfig
    fake = [LLMModelConfig("groq", "m-a", 0, ["json"])]
    expected = {"score": 85.0, "decision": "SHORTLIST"}
    with patch.object(model_registry, "get_eligible_llm_models", return_value=fake):
        with patch.object(LLMProviderFactory, "get_provider") as gp:
            gp.return_value = MagicMock(generate_json=AsyncMock(return_value=expected))
            assert run(LLMProviderFactory.generate_with_fallback("p", {})) == expected


# --- 5. Fallback: first provider fails, second succeeds ---

def test_fallback_to_second_provider():
    from app.services.llm_provider import LLMProviderFactory, LLMError
    from app.services.model_registry import model_registry, LLMModelConfig
    fake = [
        LLMModelConfig("groq", "m-a", 0, ["json"]),
        LLMModelConfig("gemini", "m-b", 1, ["json"]),
    ]
    expected = {"score": 60.0, "decision": "REVIEW"}
    providers = {
        "groq": MagicMock(generate_json=AsyncMock(side_effect=LLMError("fail"))),
        "gemini": MagicMock(generate_json=AsyncMock(return_value=expected)),
    }
    with patch.object(model_registry, "get_eligible_llm_models", return_value=fake):
        with patch.object(LLMProviderFactory, "get_provider", side_effect=lambda n: providers[n]):
            assert run(LLMProviderFactory.generate_with_fallback("p", {})) == expected


# --- 6. _is_valid_profile ---

def test_profile_empty_dict():
    from app.services.orchestrator import _is_valid_profile
    assert _is_valid_profile({}) is False

def test_profile_all_falsy():
    from app.services.orchestrator import _is_valid_profile
    assert _is_valid_profile({"name": None, "skills": [], "experience": []}) is False

def test_profile_name_only():
    from app.services.orchestrator import _is_valid_profile
    assert _is_valid_profile({"name": "Alice"}) is True

def test_profile_skills_only():
    from app.services.orchestrator import _is_valid_profile
    assert _is_valid_profile({"skills": ["Python"]}) is True

def test_profile_experience_only():
    from app.services.orchestrator import _is_valid_profile
    assert _is_valid_profile({"experience": [{"role": "Eng"}]}) is True

def test_profile_not_a_dict():
    from app.services.orchestrator import _is_valid_profile
    assert _is_valid_profile(None) is False  # type: ignore
    assert _is_valid_profile("string") is False  # type: ignore


# --- 7. evaluate_candidate: missing score raises InvalidEvaluationResultError ---

def test_eval_missing_score_raises():
    from app.services.screener import ScreenerService
    from app.services.llm_provider import InvalidEvaluationResultError
    svc = ScreenerService()
    with patch("app.services.screener.LLMProviderFactory.generate_with_fallback",
               new=AsyncMock(return_value={"decision": "REVIEW"})):
        with pytest.raises(InvalidEvaluationResultError):
            run(svc.evaluate_candidate({"title": "Eng"}, {"name": "Bob"}))

def test_eval_empty_raises():
    from app.services.screener import ScreenerService
    from app.services.llm_provider import InvalidEvaluationResultError
    svc = ScreenerService()
    with patch("app.services.screener.LLMProviderFactory.generate_with_fallback",
               new=AsyncMock(return_value={})):
        with pytest.raises(InvalidEvaluationResultError):
            run(svc.evaluate_candidate({"title": "Eng"}, {"name": "Bob"}))


# --- 8. evaluate_candidate: score=0 is a valid result ---

def test_eval_score_zero_is_valid():
    from app.services.screener import ScreenerService
    svc = ScreenerService()
    result = {"score": 0.0, "decision": "REJECT", "strengths": [], "gaps": [], "evidence": []}
    with patch("app.services.screener.LLMProviderFactory.generate_with_fallback",
               new=AsyncMock(return_value=result)):
        out = run(svc.evaluate_candidate({"title": "Eng"}, {"name": "Bob"}))
        assert out["score"] == 0.0
        assert out["decision"] == "REJECT"


# --- 9. evaluate_candidate: LLMExhaustionError propagates ---

def test_eval_exhaustion_propagates():
    from app.services.screener import ScreenerService
    from app.services.llm_provider import LLMExhaustionError
    svc = ScreenerService()
    with patch("app.services.screener.LLMProviderFactory.generate_with_fallback",
               new=AsyncMock(side_effect=LLMExhaustionError("all exhausted"))):
        with pytest.raises(LLMExhaustionError):
            run(svc.evaluate_candidate({"title": "Eng"}, {"name": "Bob"}))


# --- 10. JobResponse: skills extracted from job_profile ---

def test_job_response_skills_from_profile():
    from app.schemas.job import JobResponse
    data = {
        "id": 1, "title": "Eng", "description": "build",
        "job_profile": {"required_skills": ["Python", "FastAPI"], "preferred_skills": ["Docker"]},
    }
    resp = JobResponse.model_validate(data)
    assert resp.required_skills == ["Python", "FastAPI"]
    assert resp.preferred_skills == ["Docker"]

def test_job_response_no_job_profile():
    from app.schemas.job import JobResponse
    data = {"id": 2, "title": "Eng", "description": "build", "job_profile": None}
    resp = JobResponse.model_validate(data)
    assert resp.required_skills == []
    assert resp.preferred_skills == []
