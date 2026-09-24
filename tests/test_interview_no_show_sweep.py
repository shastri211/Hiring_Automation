from datetime import datetime, timedelta, timezone

import pytest

from app.models.job import Job
from app.models.batch import ScreeningBatch
from app.models.resume import Resume
from app.models.interview import Interview
from app.services.interview import InterviewIntegrationAdapter
from tenancy_fixtures import TEST_ORG_ID


@pytest.fixture
async def make_interview(db_session):
    """Creates a fresh Job/Resume/Interview trio per call, so each test case
    in a parametrized/multi-row test gets its own isolated row."""
    counter = {"n": 0}

    async def _make(**interview_kwargs):
        counter["n"] += 1
        n = counter["n"]
        job = Job(organization_id=TEST_ORG_ID, title=f"Test Job {n}", description="d")
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        batch = ScreeningBatch(job_id=job.id, status="COMPLETED", total_resumes=1)
        db_session.add(batch)
        await db_session.commit()
        await db_session.refresh(batch)

        resume = Resume(
            job_id=job.id,
            batch_id=batch.id,
            filename=f"resume_{n}.pdf",
            file_hash=f"hash_{n}_{id(batch)}",
            storage_key="key",
            status="PROCESSED",
        )
        db_session.add(resume)
        await db_session.commit()
        await db_session.refresh(resume)

        interview = Interview(job_id=job.id, resume_id=resume.id, **interview_kwargs)
        db_session.add(interview)
        await db_session.commit()
        await db_session.refresh(interview)
        return interview

    return _make


def _hours_ago(hours: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def _hours_from_now(hours: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


async def _status_of(db_session, interview_id: int) -> str:
    from sqlalchemy import select
    result = await db_session.execute(
        select(Interview).where(Interview.id == interview_id).execution_options(populate_existing=True)
    )
    return result.scalar_one().status


@pytest.mark.asyncio
async def test_true_first_attempt_never_started_becomes_no_show(make_interview, db_session):
    interview = await make_interview(
        status="SCHEDULED", link_expires_at=_hours_ago(1), provider_run_id=None,
    )

    await InterviewIntegrationAdapter().mark_expired_interviews_as_no_show()

    assert await _status_of(db_session, interview.id) == "NO_SHOW"


@pytest.mark.asyncio
async def test_abandoned_retry_becomes_no_show_even_though_provider_run_id_is_set(make_interview, db_session):
    """The bug this fix targets: after a retry, provider_run_id still points
    at the previous (superseded) attempt. Gating the sweep on
    provider_run_id IS NULL alone would leave this row SCHEDULED forever."""
    interview = await make_interview(
        status="SCHEDULED",
        link_expires_at=_hours_ago(1),
        provider_run_id="555",  # from the first, superseded attempt
        provider_run_attempt=0,
        retry_count=1,  # a retry happened; the new attempt never got a run recorded
    )

    await InterviewIntegrationAdapter().mark_expired_interviews_as_no_show()

    assert await _status_of(db_session, interview.id) == "NO_SHOW"


@pytest.mark.asyncio
async def test_current_generation_with_recorded_run_is_left_alone(make_interview, db_session):
    """provider_run_attempt == retry_count means the current generation
    genuinely has a recorded run - not a no-show, regardless of expiry
    (that's the in-progress/stuck-run edge case left to manual resync)."""
    interview = await make_interview(
        status="SCHEDULED",
        link_expires_at=_hours_ago(1),
        provider_run_id="555",
        provider_run_attempt=0,
        retry_count=0,
    )

    await InterviewIntegrationAdapter().mark_expired_interviews_as_no_show()

    assert await _status_of(db_session, interview.id) == "SCHEDULED"


@pytest.mark.asyncio
async def test_unexpired_link_is_left_alone(make_interview, db_session):
    interview = await make_interview(
        status="SCHEDULED", link_expires_at=_hours_from_now(1), provider_run_id=None,
    )

    await InterviewIntegrationAdapter().mark_expired_interviews_as_no_show()

    assert await _status_of(db_session, interview.id) == "SCHEDULED"


@pytest.mark.asyncio
async def test_in_progress_is_left_alone_even_if_expired(make_interview, db_session):
    """A candidate who did start moved to IN_PROGRESS - not a no-show, even
    past link_expires_at; left to manual resync if it gets stuck."""
    interview = await make_interview(
        status="IN_PROGRESS", link_expires_at=_hours_ago(1), provider_run_id=None,
    )

    await InterviewIntegrationAdapter().mark_expired_interviews_as_no_show()

    assert await _status_of(db_session, interview.id) == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_no_link_expiry_is_left_alone(make_interview, db_session):
    interview = await make_interview(status="SCHEDULED", link_expires_at=None, provider_run_id=None)

    await InterviewIntegrationAdapter().mark_expired_interviews_as_no_show()

    assert await _status_of(db_session, interview.id) == "SCHEDULED"
