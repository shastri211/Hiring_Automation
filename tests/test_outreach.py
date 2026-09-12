import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient

from app.models.settings import AppSettings


def _mock_session_local(mock_session_local):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session
    return mock_session


def _make_app_settings(**overrides):
    s = MagicMock(spec=AppSettings)
    s.id = 1
    s.auto_email_on_shortlist = False
    s.shortlist_email_template_id = None
    s.auto_email_on_interview_scheduled = False
    s.interview_scheduled_email_template_id = None
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


# -- OutreachAutomationService unit tests (mirrors test_emails.py's AsyncSessionLocal-mock pattern) --

@pytest.mark.asyncio
@patch("app.services.outreach.AsyncSessionLocal", new_callable=MagicMock)
@patch("app.services.outreach.email_service")
async def test_on_decision_shortlisted_noop_when_disabled(mock_email_service, mock_session_local):
    from app.services.outreach import outreach_service

    mock_session = _mock_session_local(mock_session_local)
    settings_exec = MagicMock()
    settings_exec.scalar_one_or_none.return_value = _make_app_settings(auto_email_on_shortlist=False)
    mock_session.execute = AsyncMock(return_value=settings_exec)
    mock_email_service.queue_bulk_emails = AsyncMock()

    await outreach_service.on_decision_shortlisted(job_id=1, resume_ids=[7])

    mock_email_service.queue_bulk_emails.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.services.outreach.AsyncSessionLocal", new_callable=MagicMock)
@patch("app.services.outreach.email_service")
async def test_on_decision_shortlisted_calls_queue_bulk_emails_when_enabled(
    mock_email_service, mock_session_local
):
    from app.services.outreach import outreach_service

    mock_session = _mock_session_local(mock_session_local)
    settings_exec = MagicMock()
    settings_exec.scalar_one_or_none.return_value = _make_app_settings(
        auto_email_on_shortlist=True, shortlist_email_template_id=42
    )
    mock_session.execute = AsyncMock(return_value=settings_exec)
    mock_email_service.queue_bulk_emails = AsyncMock()

    await outreach_service.on_decision_shortlisted(job_id=1, resume_ids=[7, 8])

    mock_email_service.queue_bulk_emails.assert_awaited_once()
    _, kwargs = mock_email_service.queue_bulk_emails.call_args
    assert kwargs["job_id"] == 1
    assert kwargs["resume_ids"] == [7, 8]
    assert kwargs["template_id"] == 42


@pytest.mark.asyncio
@patch("app.services.outreach.AsyncSessionLocal", new_callable=MagicMock)
@patch("app.services.outreach.email_service")
async def test_on_decision_shortlisted_enabled_but_no_template_skips(
    mock_email_service, mock_session_local
):
    from app.services.outreach import outreach_service

    mock_session = _mock_session_local(mock_session_local)
    settings_exec = MagicMock()
    settings_exec.scalar_one_or_none.return_value = _make_app_settings(
        auto_email_on_shortlist=True, shortlist_email_template_id=None
    )
    mock_session.execute = AsyncMock(return_value=settings_exec)
    mock_email_service.queue_bulk_emails = AsyncMock()

    await outreach_service.on_decision_shortlisted(job_id=1, resume_ids=[7])

    mock_email_service.queue_bulk_emails.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.services.outreach.AsyncSessionLocal", new_callable=MagicMock)
async def test_on_decision_shortlisted_no_settings_row_is_noop(mock_session_local):
    from app.services.outreach import outreach_service

    mock_session = _mock_session_local(mock_session_local)
    settings_exec = MagicMock()
    settings_exec.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=settings_exec)

    # Should not raise even with nothing else mocked.
    await outreach_service.on_decision_shortlisted(job_id=1, resume_ids=[7])


@pytest.mark.asyncio
async def test_on_decision_shortlisted_empty_resume_ids_is_noop():
    from app.services.outreach import outreach_service

    # No patching at all - if this touched the DB or email_service it would
    # either raise or hang; the empty-list short-circuit must return first.
    await outreach_service.on_decision_shortlisted(job_id=1, resume_ids=[])


@pytest.mark.asyncio
@patch("app.services.outreach.AsyncSessionLocal", new_callable=MagicMock)
@patch("app.services.outreach.email_service")
async def test_on_decision_shortlisted_swallows_queue_bulk_emails_failure(
    mock_email_service, mock_session_local
):
    """A failure inside outreach (e.g. bad template, missing email) must never propagate."""
    from app.services.outreach import outreach_service

    mock_session = _mock_session_local(mock_session_local)
    settings_exec = MagicMock()
    settings_exec.scalar_one_or_none.return_value = _make_app_settings(
        auto_email_on_shortlist=True, shortlist_email_template_id=42
    )
    mock_session.execute = AsyncMock(return_value=settings_exec)
    mock_email_service.queue_bulk_emails = AsyncMock(side_effect=ValueError("boom"))

    # Must not raise.
    await outreach_service.on_decision_shortlisted(job_id=1, resume_ids=[7])


@pytest.mark.asyncio
@patch("app.services.outreach.AsyncSessionLocal", new_callable=MagicMock)
@patch("app.services.outreach.email_service")
async def test_on_interview_triggered_calls_queue_bulk_emails_when_enabled(
    mock_email_service, mock_session_local
):
    from app.services.outreach import outreach_service

    mock_session = _mock_session_local(mock_session_local)
    settings_exec = MagicMock()
    settings_exec.scalar_one_or_none.return_value = _make_app_settings(
        auto_email_on_interview_scheduled=True, interview_scheduled_email_template_id=99
    )
    mock_session.execute = AsyncMock(return_value=settings_exec)
    mock_email_service.queue_bulk_emails = AsyncMock()

    await outreach_service.on_interview_triggered(job_id=1, resume_id=7)

    mock_email_service.queue_bulk_emails.assert_awaited_once()
    _, kwargs = mock_email_service.queue_bulk_emails.call_args
    assert kwargs["job_id"] == 1
    assert kwargs["resume_ids"] == [7]
    assert kwargs["template_id"] == 99


# -- Endpoint-level wiring (decision endpoints live in app/api/jobs.py, tested under
# test_results_api.py by existing convention; outreach-specific wiring assertions are
# kept together here rather than added to test_jobs.py, which doesn't cover decision
# endpoints today) --------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_decision_shortlist_triggers_outreach(client: AsyncClient):
    from app.api import jobs
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[jobs.get_db] = mock_get_db

    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.screening import ScreeningResult
    from app.models.profile import CandidateProfile
    import datetime

    job = MagicMock(spec=Job)
    job.id = 1
    job.title = "SWE"
    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = job

    resume = MagicMock(spec=Resume)
    resume.id = 1
    resume.job_id = 1
    resume.filename = "test.pdf"
    resume.status = "READY"
    resume.error_message = None
    resume_exec = MagicMock()
    resume_exec.scalar_one_or_none.return_value = resume

    sr = MagicMock(spec=ScreeningResult)
    sr.id = 1
    sr.job_id = 1
    sr.resume_id = 1
    sr.score = 85.0
    sr.semantic_score = 85.0
    sr.strengths = []
    sr.gaps = []
    sr.evidence = []
    sr.decision = "REVIEW"
    sr.notes = None
    sr.created_at = datetime.datetime.utcnow()
    sr_exec = MagicMock()
    sr_exec.scalar_one_or_none.return_value = sr

    profile_exec = MagicMock()
    profile_exec.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(side_effect=[job_exec, resume_exec, sr_exec, profile_exec])

    with patch("app.api.jobs.outreach_service.on_decision_shortlisted", new_callable=AsyncMock) as mock_outreach:
        try:
            response = await client.patch("/jobs/1/results/1/decision", json={"decision": "SHORTLIST"})
            assert response.status_code == 200
            mock_outreach.assert_awaited_once_with(1, [1])
        finally:
            fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_single_decision_review_does_not_trigger_outreach(client: AsyncClient):
    from app.api import jobs
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[jobs.get_db] = mock_get_db

    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.screening import ScreeningResult
    import datetime

    job = MagicMock(spec=Job)
    job.id = 1
    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = job

    resume = MagicMock(spec=Resume)
    resume.id = 1
    resume.job_id = 1
    resume.filename = "test.pdf"
    resume.status = "READY"
    resume.error_message = None
    resume_exec = MagicMock()
    resume_exec.scalar_one_or_none.return_value = resume

    sr = MagicMock(spec=ScreeningResult)
    sr.id = 1
    sr.job_id = 1
    sr.resume_id = 1
    sr.score = 85.0
    sr.semantic_score = 85.0
    sr.strengths = []
    sr.gaps = []
    sr.evidence = []
    sr.decision = "SHORTLIST"
    sr.notes = None
    sr.created_at = datetime.datetime.utcnow()
    sr_exec = MagicMock()
    sr_exec.scalar_one_or_none.return_value = sr

    profile_exec = MagicMock()
    profile_exec.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(side_effect=[job_exec, resume_exec, sr_exec, profile_exec])

    with patch("app.api.jobs.outreach_service.on_decision_shortlisted", new_callable=AsyncMock) as mock_outreach:
        try:
            response = await client.patch("/jobs/1/results/1/decision", json={"decision": "REVIEW"})
            assert response.status_code == 200
            mock_outreach.assert_not_awaited()
        finally:
            fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_bulk_decision_shortlist_triggers_outreach(client: AsyncClient):
    from app.api import jobs
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[jobs.get_db] = mock_get_db

    from app.models.job import Job
    from app.models.screening import ScreeningResult

    job = MagicMock(spec=Job)
    job.id = 1
    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = job

    sr1 = MagicMock(spec=ScreeningResult)
    sr1.id = 1
    sr1.resume_id = 7
    sr2 = MagicMock(spec=ScreeningResult)
    sr2.id = 2
    sr2.resume_id = 8

    screenings_exec = MagicMock()
    screenings_exec.scalars.return_value.all.return_value = [sr1, sr2]

    mock_db.execute = AsyncMock(side_effect=[job_exec, screenings_exec])
    mock_db.commit = AsyncMock()

    with patch("app.api.jobs.outreach_service.on_decision_shortlisted", new_callable=AsyncMock) as mock_outreach:
        try:
            response = await client.patch(
                "/jobs/1/results/bulk-decision",
                json={"resume_ids": [7, 8], "decision": "SHORTLIST"},
            )
            assert response.status_code == 200
            mock_outreach.assert_awaited_once_with(1, [7, 8])
        finally:
            fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_decision_endpoint_survives_outreach_failure_end_to_end(client: AsyncClient):
    """Not mocking on_decision_shortlisted itself - patching AsyncSessionLocal inside
    app.services.outreach to raise, proving the try/except in the real service
    protects the caller (not just at the unit-test level)."""
    from app.api import jobs
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[jobs.get_db] = mock_get_db

    from app.models.job import Job
    from app.models.resume import Resume
    from app.models.screening import ScreeningResult
    import datetime

    job = MagicMock(spec=Job)
    job.id = 1
    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = job

    resume = MagicMock(spec=Resume)
    resume.id = 1
    resume.job_id = 1
    resume.filename = "test.pdf"
    resume.status = "READY"
    resume.error_message = None
    resume_exec = MagicMock()
    resume_exec.scalar_one_or_none.return_value = resume

    sr = MagicMock(spec=ScreeningResult)
    sr.id = 1
    sr.job_id = 1
    sr.resume_id = 1
    sr.score = 85.0
    sr.semantic_score = 85.0
    sr.strengths = []
    sr.gaps = []
    sr.evidence = []
    sr.decision = "REVIEW"
    sr.notes = None
    sr.created_at = datetime.datetime.utcnow()
    sr_exec = MagicMock()
    sr_exec.scalar_one_or_none.return_value = sr

    profile_exec = MagicMock()
    profile_exec.scalar_one_or_none.return_value = None

    mock_db.execute = AsyncMock(side_effect=[job_exec, resume_exec, sr_exec, profile_exec])

    with patch("app.services.outreach.AsyncSessionLocal", side_effect=RuntimeError("db down")):
        try:
            response = await client.patch("/jobs/1/results/1/decision", json={"decision": "SHORTLIST"})
            assert response.status_code == 200
        finally:
            fastapi_app.dependency_overrides.clear()
