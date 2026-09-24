"""Public candidate apply link: app/api/public_application.py,
app/services/public_application.py, and the recruiter link controls in
app/api/jobs.py.

No external calls: Redis (rate limiter + queue) is replaced by in-memory
fakes, file storage goes to a per-test tmp dir, and the orchestrator's
extractor/profiler/embedding/Qdrant boundaries are mocked. Postgres is the
real test_isolation schema (see conftest.py).
"""
import asyncio
import io
import os
import secrets
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.batch import ScreeningBatch
from app.models.job import Job
from app.models.profile import CandidateProfile
from app.models.public_application import PublicApplicationSubmission
from app.models.resume import Resume
from app.services import rate_limit
from app.services.public_application import requeue_unenqueued_applications
from app.services.storage import storage_service
from tenancy_fixtures import TEST_ORG_ID

PDF = "application/pdf"


# -- fixtures -----------------------------------------------------------------

class _FakeRateLimiter:
    """In-memory stand-in for rate_limit.check - records every key hit."""

    def __init__(self):
        self.counts = {}
        self.keys_checked = []
        self.unavailable = False

    async def check(self, key, limit, window_seconds):
        if self.unavailable:
            raise rate_limit.RateLimiterUnavailable("redis down")
        self.keys_checked.append(key)
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key] <= limit, 1234


@pytest.fixture
def fake_limiter():
    limiter = _FakeRateLimiter()
    with patch("app.api.public_application.rate_limit.check", side_effect=limiter.check):
        yield limiter


@pytest.fixture
def mock_enqueue():
    with patch("app.services.public_application.queue_service.enqueue_resume", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture
def tmp_storage(tmp_path):
    with patch.object(storage_service, "base_dir", str(tmp_path)):
        yield tmp_path


async def _make_job(db_session, *, status="ACTIVE", token=True) -> Job:
    job = Job(
        organization_id=TEST_ORG_ID,
        title="Platform Engineer",
        description="Build and run the platform.",
        job_profile={
            "title": "Platform Engineer",
            "role_summary": "Own the platform.",
            "responsibilities": ["Run infra", "On-call"],
            "required_skills": ["python"],
        },
        status=status,
        embedding_profile="internal-embedding-model",
        application_token=secrets.token_urlsafe(32) if token else None,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


def _form(**overrides):
    data = {"name": "Ada Applicant", "email": "ada@example.com", "phone": "+1 555 0100", "consent": "true"}
    data.update(overrides)
    return {k: v for k, v in data.items() if v is not None}


def _file(content: bytes = None, name="resume.pdf", ctype=PDF):
    content = content if content is not None else f"%PDF-1.4 {secrets.token_hex(16)}".encode()
    return {"file": (name, io.BytesIO(content), ctype)}


async def _count(db_session, model, *where):
    return (await db_session.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


# -- GET /public/jobs/{token} -------------------------------------------------

async def test_get_public_job_returns_only_public_fields(client: AsyncClient, db_session):
    job = await _make_job(db_session)
    res = await client.get(f"/public/jobs/{job.application_token}")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"title", "role_summary", "responsibilities", "description"}
    assert body["title"] == "Platform Engineer"
    assert body["role_summary"] == "Own the platform."
    assert body["responsibilities"] == ["Run infra", "On-call"]


async def test_get_public_job_unknown_token_404(client: AsyncClient):
    res = await client.get(f"/public/jobs/{secrets.token_urlsafe(32)}")
    assert res.status_code == 404
    assert res.json()["detail"] == {"reason": "not_found"}


async def test_closed_and_rotated_links_return_404(client: AsyncClient, db_session):
    job = await _make_job(db_session, token=False)

    opened = (await client.post(f"/jobs/{job.id}/application-link")).json()
    first_token = opened["application_token"]
    assert first_token
    # Opening again is idempotent.
    assert (await client.post(f"/jobs/{job.id}/application-link")).json()["application_token"] == first_token
    assert (await client.get(f"/public/jobs/{first_token}")).status_code == 200

    rotated = (await client.post(f"/jobs/{job.id}/application-link/rotate")).json()
    second_token = rotated["application_token"]
    assert second_token and second_token != first_token
    assert (await client.get(f"/public/jobs/{first_token}")).status_code == 404
    assert (await client.get(f"/public/jobs/{second_token}")).status_code == 200

    closed = (await client.delete(f"/jobs/{job.id}/application-link")).json()
    assert closed["application_token"] is None
    assert closed["application_url"] is None
    res = await client.get(f"/public/jobs/{second_token}")
    assert res.status_code == 404
    assert res.json()["detail"] == {"reason": "not_found"}


async def test_current_token_on_paused_job_returns_410(client: AsyncClient, db_session):
    job = await _make_job(db_session, status="PAUSED")
    res = await client.get(f"/public/jobs/{job.application_token}")
    assert res.status_code == 410
    assert res.json()["detail"] == {"reason": "closed"}


async def test_application_url_uses_public_base_url(client: AsyncClient, db_session):
    job = await _make_job(db_session, token=False)
    with patch("app.core.config.settings.PUBLIC_APP_BASE_URL", "https://app.example.com"):
        body = (await client.post(f"/jobs/{job.id}/application-link")).json()
    assert body["application_url"] == f"https://app.example.com/apply/{body['application_token']}"


async def test_link_endpoints_require_auth(client: AsyncClient, db_session):
    from app.main import app
    from app.api.deps import get_authenticated_user, get_current_user

    job = await _make_job(db_session, token=False)
    override = app.dependency_overrides.pop(get_current_user)
    auth_override = app.dependency_overrides.pop(get_authenticated_user)
    try:
        assert (await client.post(f"/jobs/{job.id}/application-link")).status_code == 401
        assert (await client.post(f"/jobs/{job.id}/application-link/rotate")).status_code == 401
        assert (await client.delete(f"/jobs/{job.id}/application-link")).status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = override
        app.dependency_overrides[get_authenticated_user] = auth_override


# -- POST /public/jobs/{token}/apply ------------------------------------------

async def test_apply_happy_path(client, db_session, fake_limiter, mock_enqueue, tmp_storage):
    job = await _make_job(db_session)
    res = await client.post(f"/public/jobs/{job.application_token}/apply", data=_form(), files=_file())
    assert res.status_code == 202
    assert res.json() == {"status": "received"}

    resume = (await db_session.execute(select(Resume).where(Resume.job_id == job.id))).scalar_one()
    batch = (await db_session.execute(select(ScreeningBatch).where(ScreeningBatch.id == resume.batch_id))).scalar_one()
    sub = (
        await db_session.execute(select(PublicApplicationSubmission).where(PublicApplicationSubmission.resume_id == resume.id))
    ).scalar_one()

    assert batch.batch_type == "APPLICATION"
    assert batch.total_resumes == 1
    assert sub.applicant_name == "Ada Applicant"
    assert sub.applicant_email == "ada@example.com"
    assert sub.applicant_phone == "+1 555 0100"
    assert sub.consent_at is not None
    assert sub.enqueued_at is not None
    mock_enqueue.assert_awaited_once_with(resume.id, job_id=job.id, batch_id=batch.id)
    assert os.path.exists(os.path.join(tmp_storage, resume.storage_key))
    # Self-reported data never leaks into the extracted profile.
    assert await _count(db_session, CandidateProfile, CandidateProfile.resume_id == resume.id) == 0


async def test_apply_duplicate_same_job_is_generic_202_with_no_new_rows(
    client, db_session, fake_limiter, mock_enqueue, tmp_storage
):
    job = await _make_job(db_session)
    content = f"%PDF dup {secrets.token_hex(8)}".encode()
    url = f"/public/jobs/{job.application_token}/apply"

    assert (await client.post(url, data=_form(), files=_file(content))).status_code == 202
    res = await client.post(url, data=_form(email="other@example.com"), files=_file(content))
    assert res.status_code == 202
    assert res.json() == {"status": "received"}

    assert await _count(db_session, Resume, Resume.job_id == job.id) == 1
    assert await _count(db_session, ScreeningBatch, ScreeningBatch.job_id == job.id) == 1
    assert await _count(db_session, PublicApplicationSubmission, PublicApplicationSubmission.job_id == job.id) == 1
    assert mock_enqueue.await_count == 1


async def test_same_file_to_two_jobs_creates_two_applications(
    client, db_session, fake_limiter, mock_enqueue, tmp_storage
):
    job_a = await _make_job(db_session)
    job_b = await _make_job(db_session)
    content = f"%PDF multi {secrets.token_hex(8)}".encode()

    for job in (job_a, job_b):
        res = await client.post(f"/public/jobs/{job.application_token}/apply", data=_form(), files=_file(content))
        assert res.status_code == 202

    for job in (job_a, job_b):
        assert await _count(db_session, Resume, Resume.job_id == job.id) == 1
        assert await _count(db_session, PublicApplicationSubmission, PublicApplicationSubmission.job_id == job.id) == 1
    assert mock_enqueue.await_count == 2


@pytest.mark.parametrize(
    "file_kwargs",
    [
        {"name": "resume.txt", "ctype": "text/plain"},
        {"name": "resume.zip", "ctype": "application/zip"},
        {"content": b""},
    ],
)
async def test_apply_rejects_invalid_file(client, db_session, fake_limiter, mock_enqueue, tmp_storage, file_kwargs):
    job = await _make_job(db_session)
    res = await client.post(f"/public/jobs/{job.application_token}/apply", data=_form(), files=_file(**file_kwargs))
    assert res.status_code == 400
    assert res.json()["detail"]["reason"] == "invalid_file"
    assert await _count(db_session, Resume, Resume.job_id == job.id) == 0
    assert await _count(db_session, ScreeningBatch, ScreeningBatch.job_id == job.id) == 0
    mock_enqueue.assert_not_awaited()


async def test_apply_rejects_oversized_file(client, db_session, fake_limiter, mock_enqueue, tmp_storage):
    job = await _make_job(db_session)
    with patch("app.services.resume_intake.MAX_RESUME_FILE_SIZE_BYTES", 10):
        res = await client.post(
            f"/public/jobs/{job.application_token}/apply", data=_form(), files=_file(b"x" * 11)
        )
    assert res.status_code == 400
    mock_enqueue.assert_not_awaited()


@pytest.mark.parametrize(
    "form_overrides, reason",
    [
        ({"consent": "false"}, "consent_required"),
        ({"email": "not-an-email"}, "invalid_email"),
        ({"name": "   "}, "invalid_name"),
        ({"phone": "1" * 51}, "invalid_phone"),
    ],
)
async def test_apply_field_validation(client, db_session, fake_limiter, mock_enqueue, tmp_storage, form_overrides, reason):
    job = await _make_job(db_session)
    res = await client.post(
        f"/public/jobs/{job.application_token}/apply", data=_form(**form_overrides), files=_file()
    )
    assert res.status_code == 422
    assert res.json()["detail"] == {"reason": reason}
    assert await _count(db_session, Resume, Resume.job_id == job.id) == 0


async def test_apply_missing_consent_field_is_422(client, db_session, fake_limiter, mock_enqueue):
    job = await _make_job(db_session)
    res = await client.post(
        f"/public/jobs/{job.application_token}/apply", data=_form(consent=None), files=_file()
    )
    assert res.status_code == 422


async def test_honeypot_returns_generic_202_and_stores_nothing(
    client, db_session, fake_limiter, mock_enqueue, tmp_storage
):
    job = await _make_job(db_session)
    res = await client.post(
        f"/public/jobs/{job.application_token}/apply", data=_form(website="http://spam"), files=_file()
    )
    assert res.status_code == 202
    assert res.json() == {"status": "received"}
    assert await _count(db_session, Resume, Resume.job_id == job.id) == 0
    assert await _count(db_session, ScreeningBatch, ScreeningBatch.job_id == job.id) == 0
    mock_enqueue.assert_not_awaited()
    # Still counted against the per-IP limit.
    assert any(k.startswith("apply:ip:") for k in fake_limiter.keys_checked)


async def test_apply_to_closed_or_paused_job(client, db_session, fake_limiter, mock_enqueue):
    paused = await _make_job(db_session, status="PAUSED")
    res = await client.post(f"/public/jobs/{paused.application_token}/apply", data=_form(), files=_file())
    assert res.status_code == 410

    res = await client.post(f"/public/jobs/{secrets.token_urlsafe(32)}/apply", data=_form(), files=_file())
    assert res.status_code == 404
    mock_enqueue.assert_not_awaited()


# -- rate limiting --------------------------------------------------------------

async def test_ip_limit_runs_before_token_lookup(client, db_session, fake_limiter, mock_enqueue):
    """Over-limit IP is refused even for an unknown token, without touching
    the DB, and an unknown token never creates a per-job counter."""
    unknown = secrets.token_urlsafe(32)
    with patch("app.core.config.settings.PUBLIC_APPLY_MAX_PER_IP_PER_HOUR", 1):
        first = await client.post(f"/public/jobs/{unknown}/apply", data=_form(), files=_file())
        assert first.status_code == 404
        with patch(
            "app.api.public_application._get_job_by_token_or_typed_error", new_callable=AsyncMock
        ) as lookup:
            second = await client.post(f"/public/jobs/{unknown}/apply", data=_form(), files=_file())
            lookup.assert_not_awaited()
    assert second.status_code == 429
    assert second.headers["Retry-After"] == "1234"
    assert not any(k.startswith("apply:job:") for k in fake_limiter.keys_checked)


async def test_per_job_limit_keyed_on_resolved_job(client, db_session, fake_limiter, mock_enqueue, tmp_storage):
    job = await _make_job(db_session)
    url = f"/public/jobs/{job.application_token}/apply"
    with patch("app.core.config.settings.PUBLIC_APPLY_MAX_PER_JOB_PER_HOUR", 1):
        assert (await client.post(url, data=_form(), files=_file())).status_code == 202
        res = await client.post(url, data=_form(), files=_file())
    assert res.status_code == 429
    assert res.json()["detail"] == {"reason": "rate_limited"}
    assert f"apply:job:{job.id}" in fake_limiter.keys_checked
    # Key uses the job id, never the raw token.
    assert not any(job.application_token in k for k in fake_limiter.keys_checked)
    assert await _count(db_session, Resume, Resume.job_id == job.id) == 1


async def test_rate_limiter_unavailable_fails_closed(client, db_session, fake_limiter, mock_enqueue):
    job = await _make_job(db_session)
    fake_limiter.unavailable = True
    res = await client.post(f"/public/jobs/{job.application_token}/apply", data=_form(), files=_file())
    assert res.status_code == 503
    assert res.json()["detail"] == {"reason": "temporarily_unavailable"}
    assert await _count(db_session, Resume, Resume.job_id == job.id) == 0


async def test_rate_limit_check_counts_in_fixed_window():
    """The real rate_limit.check against a fake Redis pipeline."""
    store = {}

    class _Pipe:
        def __init__(self):
            self.ops = []

        def incr(self, key):
            self.ops.append(key)

        def expire(self, key, ttl):
            pass

        async def execute(self):
            key = self.ops[0]
            store[key] = store.get(key, 0) + 1
            return [store[key], True]

    fake_client = MagicMock()
    fake_client.pipeline.side_effect = lambda transaction=True: _Pipe()
    with patch.object(rate_limit.queue_service, "redis_client", fake_client):
        results = [await rate_limit.check("k", 2, 3600) for _ in range(3)]
    assert [r[0] for r in results] == [True, True, False]
    assert all(1 <= r[1] <= 3600 for r in results)

    broken = MagicMock()
    broken.pipeline.side_effect = ConnectionError("down")
    with patch.object(rate_limit.queue_service, "redis_client", broken):
        with pytest.raises(rate_limit.RateLimiterUnavailable):
            await rate_limit.check("k", 2, 3600)


# -- enqueue reliability + recovery sweep ---------------------------------------

async def _age_submissions(db_session, job_id, seconds=3600):
    await db_session.execute(
        update(PublicApplicationSubmission)
        .where(PublicApplicationSubmission.job_id == job_id)
        .values(created_at=datetime.now(timezone.utc) - timedelta(seconds=seconds))
    )
    await db_session.commit()


async def test_enqueue_failure_keeps_rows_and_returns_received(
    client, db_session, fake_limiter, mock_enqueue, tmp_storage, caplog
):
    job = await _make_job(db_session)
    mock_enqueue.side_effect = ConnectionError("redis blip")
    with caplog.at_level("WARNING", logger="app.services.public_application"):
        res = await client.post(f"/public/jobs/{job.application_token}/apply", data=_form(), files=_file())
    assert res.status_code == 202
    sub = (
        await db_session.execute(select(PublicApplicationSubmission).where(PublicApplicationSubmission.job_id == job.id))
    ).scalar_one()
    assert sub.enqueued_at is None
    assert await _count(db_session, Resume, Resume.job_id == job.id) == 1
    assert "recovery sweep will re-enqueue" in caplog.text
    # PII stays out of logs.
    assert "ada@example.com" not in caplog.text and "Ada Applicant" not in caplog.text


async def test_sweep_requeues_once_and_respects_filters(client, db_session, fake_limiter, mock_enqueue, tmp_storage):
    active = await _make_job(db_session)
    paused = await _make_job(db_session)
    mock_enqueue.side_effect = ConnectionError("redis blip")
    for job in (active, paused):
        assert (await client.post(f"/public/jobs/{job.application_token}/apply", data=_form(), files=_file())).status_code == 202
    mock_enqueue.side_effect = None
    mock_enqueue.reset_mock()

    # Too young: not swept yet.
    assert await requeue_unenqueued_applications(db_session) == 0

    await _age_submissions(db_session, active.id)
    await _age_submissions(db_session, paused.id)
    paused.status = "PAUSED"
    await db_session.commit()

    # Sweep failing to enqueue leaves the row for the next pass.
    mock_enqueue.side_effect = ConnectionError("still down")
    assert await requeue_unenqueued_applications(db_session) == 0
    mock_enqueue.side_effect = None
    mock_enqueue.reset_mock()

    assert await requeue_unenqueued_applications(db_session) == 1
    active_resume = (await db_session.execute(select(Resume).where(Resume.job_id == active.id))).scalar_one()
    mock_enqueue.assert_awaited_once_with(active_resume.id, job_id=active.id, batch_id=active_resume.batch_id)

    # Marked: the next pass does nothing.
    mock_enqueue.reset_mock()
    assert await requeue_unenqueued_applications(db_session) == 0
    mock_enqueue.assert_not_awaited()

    # A resume already past UPLOADED is never swept, even if unmarked.
    await db_session.execute(
        update(PublicApplicationSubmission)
        .where(PublicApplicationSubmission.job_id == active.id)
        .values(enqueued_at=None)
    )
    active_resume.status = "PROCESSING"
    await db_session.commit()
    assert await requeue_unenqueued_applications(db_session) == 0
    mock_enqueue.assert_not_awaited()


async def test_resume_job_requeues_uploaded_application_resumes(
    client, db_session, fake_limiter, mock_enqueue, tmp_storage
):
    job = await _make_job(db_session)
    assert (await client.post(f"/public/jobs/{job.application_token}/apply", data=_form(), files=_file())).status_code == 202
    resume = (await db_session.execute(select(Resume).where(Resume.job_id == job.id))).scalar_one()
    job.status = "PAUSED"
    await db_session.commit()

    with patch("app.api.jobs.queue_service.enqueue_resume", new_callable=AsyncMock) as jobs_enqueue:
        res = await client.post(f"/jobs/{job.id}/resume")
    assert res.status_code == 200
    jobs_enqueue.assert_awaited_once_with(resume.id, job_id=job.id, batch_id=resume.batch_id)


def _orchestrator_mocks():
    return (
        patch("app.services.orchestrator.get_extractor"),
        patch("app.services.orchestrator.LocalProfilerService.profile_candidate"),
        patch("app.services.orchestrator.profiler_service.profile_candidate", new_callable=AsyncMock),
        patch("app.services.orchestrator.embedding_router.generate_embedding", new_callable=AsyncMock),
        patch("app.services.orchestrator.vector_store.create_collection", new_callable=AsyncMock),
        patch("app.services.orchestrator.vector_store.add_points", new_callable=AsyncMock),
        patch("app.services.orchestrator.resume_reuse.get_reusable_embedding", new_callable=AsyncMock, return_value=None),
    )


async def test_xadd_succeeds_then_enqueued_at_commit_fails_duplicate_is_safe(
    client, db_session, fake_limiter, mock_enqueue, tmp_storage
):
    """The message IS queued but enqueued_at never gets recorded. The sweep
    then enqueues the same resume a second time; processing both messages
    must still produce exactly one profile, one extraction, one embedding."""
    job = await _make_job(db_session)

    original_commit = AsyncSession.commit
    state = {"enqueued": False, "failed": False}

    async def _enqueue_ok(*args, **kwargs):
        state["enqueued"] = True

    async def _flaky_commit(self):
        if state["enqueued"] and not state["failed"]:
            state["failed"] = True
            raise ConnectionError("db blip right after XADD")
        return await original_commit(self)

    mock_enqueue.side_effect = _enqueue_ok
    with patch.object(AsyncSession, "commit", _flaky_commit):
        res = await client.post(f"/public/jobs/{job.application_token}/apply", data=_form(), files=_file())
    assert res.status_code == 202
    assert state["failed"] is True
    assert mock_enqueue.await_count == 1

    resume = (await db_session.execute(select(Resume).where(Resume.job_id == job.id))).scalar_one()
    sub = (
        await db_session.execute(select(PublicApplicationSubmission).where(PublicApplicationSubmission.resume_id == resume.id))
    ).scalar_one()
    assert sub.enqueued_at is None

    await _age_submissions(db_session, job.id)
    assert await requeue_unenqueued_applications(db_session) == 1
    assert mock_enqueue.await_count == 2
    resume_id = resume.id
    assert mock_enqueue.await_args_list[0].args[0] == mock_enqueue.await_args_list[1].args[0] == resume_id
    sub = (
        await db_session.execute(
            select(PublicApplicationSubmission)
            .where(PublicApplicationSubmission.resume_id == resume_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert sub.enqueued_at is not None

    # Both queued messages get processed by the real orchestrator.
    from app.services.orchestrator import orchestrator

    mocks = _orchestrator_mocks()
    with mocks[0] as get_extractor, mocks[1] as local_profile, mocks[2] as llm_profile, \
            mocks[3] as embed, mocks[4], mocks[5] as add_points, mocks[6]:
        extractor = AsyncMock()
        extractor.extract.return_value = "Ada Applicant\nada@resume.example\nPython engineer"
        get_extractor.return_value = extractor
        local_profile.return_value = (
            {"name": "Ada Applicant", "contact": {"email": "ada@resume.example"}, "skills": ["python"]},
            "canonical text",
            {"is_insufficient": False},
        )
        embed.return_value = ([0.1, 0.2], MagicMock(collection="test", dimensions=2, metric="cosine"))

        await orchestrator.process_candidate(resume_id)
        await orchestrator.process_candidate(resume_id)

    resume = (
        await db_session.execute(
            select(Resume).where(Resume.id == resume_id).execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert resume.status == "READY"
    assert await _count(db_session, CandidateProfile, CandidateProfile.resume_id == resume.id) == 1
    assert await _count(db_session, Resume, Resume.job_id == job.id) == 1
    extractor.extract.assert_awaited_once()
    llm_profile.assert_not_awaited()
    embed.assert_awaited_once()
    add_points.assert_awaited_once()
    # Profile holds extracted evidence, not the self-reported form email.
    profile = (await db_session.execute(select(CandidateProfile).where(CandidateProfile.resume_id == resume.id))).scalar_one()
    assert profile.email == "ada@resume.example"


# -- concurrency -----------------------------------------------------------------

async def test_concurrent_duplicate_application_same_file_same_job(
    client, db_session, fake_limiter, mock_enqueue, tmp_storage
):
    """Both requests pass the app-level dup pre-check before either inserts;
    the (job_id, file_hash) constraint picks one winner. The loser's batch is
    rolled back and its already-written file removed."""
    job = await _make_job(db_session)
    content = f"%PDF race {secrets.token_hex(8)}".encode()
    url = f"/public/jobs/{job.application_token}/apply"

    barrier = asyncio.Barrier(2)
    original_save = storage_service.save_file

    async def _save_then_wait(*args, **kwargs):
        key = await original_save(*args, **kwargs)
        await barrier.wait()
        return key

    with patch.object(storage_service, "save_file", side_effect=_save_then_wait):
        results = await asyncio.wait_for(
            asyncio.gather(
                client.post(url, data=_form(), files=_file(content)),
                client.post(url, data=_form(), files=_file(content)),
            ),
            timeout=30,
        )

    assert [r.status_code for r in results] == [202, 202]
    assert all(r.json() == {"status": "received"} for r in results)
    assert await _count(db_session, Resume, Resume.job_id == job.id) == 1
    assert await _count(db_session, PublicApplicationSubmission, PublicApplicationSubmission.job_id == job.id) == 1
    assert await _count(db_session, ScreeningBatch, ScreeningBatch.job_id == job.id) == 1
    assert mock_enqueue.await_count == 1

    winner = (await db_session.execute(select(Resume).where(Resume.job_id == job.id))).scalar_one()
    stored = [os.path.relpath(os.path.join(root, f), tmp_storage) for root, _, files in os.walk(tmp_storage) for f in files]
    assert [os.path.normpath(p) for p in stored] == [os.path.normpath(winner.storage_key)]


# -- recruiter-facing surfaces ------------------------------------------------------

async def test_candidate_detail_includes_self_reported_contact(
    client, db_session, fake_limiter, mock_enqueue, tmp_storage
):
    job = await _make_job(db_session)
    assert (await client.post(f"/public/jobs/{job.application_token}/apply", data=_form(), files=_file())).status_code == 202
    resume = (await db_session.execute(select(Resume).where(Resume.job_id == job.id))).scalar_one()

    body = (await client.get(f"/jobs/{job.id}/results/{resume.id}")).json()
    contact = body["self_reported_contact"]
    assert contact["name"] == "Ada Applicant"
    assert contact["email"] == "ada@example.com"
    assert contact["phone"] == "+1 555 0100"
    assert contact["submitted_at"]


async def test_delete_job_removes_submissions(client, db_session, fake_limiter, mock_enqueue, tmp_storage):
    job = await _make_job(db_session)
    job.embedding_profile = None
    await db_session.commit()
    assert (await client.post(f"/public/jobs/{job.application_token}/apply", data=_form(), files=_file())).status_code == 202
    assert await _count(db_session, PublicApplicationSubmission, PublicApplicationSubmission.job_id == job.id) == 1

    res = await client.delete(f"/jobs/{job.id}")
    assert res.status_code == 204
    assert await _count(db_session, PublicApplicationSubmission, PublicApplicationSubmission.job_id == job.id) == 0
    assert await _count(db_session, Resume, Resume.job_id == job.id) == 0
