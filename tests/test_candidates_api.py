from types import SimpleNamespace

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient

def _make_screening_result(id=1, job_id=1, resume_id=1, score=85.0, decision="SHORTLIST"):
    from app.models.screening import ScreeningResult
    sr = MagicMock(spec=ScreeningResult)
    sr.id = id
    sr.job_id = job_id
    sr.resume_id = resume_id
    sr.score = score
    sr.semantic_score = score
    sr.strengths = []
    sr.gaps = []
    sr.evidence = []
    sr.decision = decision
    sr.notes = None
    import datetime
    sr.created_at = datetime.datetime.utcnow()
    return sr

def _make_resume(id=1, job_id=1, filename="test.pdf", status="READY"):
    from app.models.resume import Resume
    r = MagicMock(spec=Resume)
    r.id = id
    r.job_id = job_id
    r.filename = filename
    r.status = status
    r.error_message = None
    return r

def _make_job(id=1, title="SWE"):
    from app.models.job import Job
    j = MagicMock(spec=Job)
    j.id = id
    j.title = title
    return j


@pytest.mark.asyncio
async def test_get_global_candidates_visibility(client: AsyncClient):
    """Verify READY candidates without ScreeningResult are included."""
    
    # We need to mock the count query result and the rows query result
    count_exec = MagicMock()
    count_exec.scalar_one.return_value = 2

    rows_exec = MagicMock()

    # Phase 6: the query now selects (ScreeningResult, job_title,
    # resume_status, error_message, resume_id, job_id) - candidate name
    # resolution moved to the separate, batched get_candidate_summaries
    # call, mocked below rather than simulated through mock_db.execute.
    sr1 = _make_screening_result(id=1, job_id=1, resume_id=1, score=90.0, decision="SHORTLIST")
    sr2 = None # Second candidate has no ScreeningResult (e.g. failed or out of bounds)

    row1 = SimpleNamespace(ScreeningResult=sr1, job_title="Job1", resume_status="READY", error_message=None, resume_id=1, job_id=1)
    row2 = SimpleNamespace(ScreeningResult=sr2, job_title="Job1", resume_status="READY", error_message=None, resume_id=2, job_id=1)

    rows_exec.all.return_value = [row1, row2]

    mock_db = AsyncMock()
    mock_db.execute.side_effect = [count_exec, rows_exec]

    async def mock_get_db_gen():
        yield mock_db

    from app.main import app
    from app.api import candidates
    app.dependency_overrides[candidates.get_db] = mock_get_db_gen

    summaries = {
        1: {"display_name": "Alice", "candidate_id": 101, "applications_count": 1, "profile_name": "Alice"},
        2: {"display_name": "Bob", "candidate_id": 102, "applications_count": 1, "profile_name": "Bob"},
    }
    with patch("app.api.candidates.get_candidate_summaries", new_callable=AsyncMock, return_value=summaries):
        response = await client.get("/candidates/")

    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    
    # First item has screening result
    assert data["items"][0]["decision"] == "SHORTLIST"
    assert data["items"][0]["resume_id"] == 1
    
    # Second item has no screening result, but still appears!
    assert data["items"][1]["decision"] is None
    assert data["items"][1]["score"] is None
    assert data["items"][1]["resume_id"] == 2
    assert data["items"][1]["status"] == "READY"
