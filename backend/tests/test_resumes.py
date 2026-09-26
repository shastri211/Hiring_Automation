import io

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock

from app.models.job import Job
from tenancy_fixtures import TEST_ORG_ID


@pytest.fixture
def mock_upload_io():
    """Uploads that get past validation would otherwise write a real file
    under uploads/ and enqueue a real Redis message - both hit the live dev
    filesystem/queue on every test run, since `client`/`db_session` exercise
    the real app rather than a mocked one. The worker then endlessly retries
    these fake "resumes" (plain placeholder bytes, not real PDFs/DOCXs)
    until it gives up, spamming its own log. Faking just these two I/O
    boundaries stops that, while still exercising this endpoint's real
    validation/dedup/DB logic end-to-end exactly as before."""
    with patch("app.api.resumes.storage_service.save_file", new_callable=AsyncMock) as mock_save, \
         patch("app.api.resumes.queue_service.enqueue_resume", new_callable=AsyncMock) as mock_enqueue:
        mock_save.side_effect = lambda file, prefix, filename_override=None: f"{prefix}/{filename_override or file.filename}"
        yield mock_save, mock_enqueue


@pytest.mark.asyncio
async def test_bulk_upload_resumes(client: AsyncClient, db_session, mock_upload_io):
    job = Job(
        organization_id=TEST_ORG_ID,
        title="Test Upload Job",
        description="Testing resume upload",
        job_profile={"title": "Test Upload Job"},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    files = [
        (
            "files",
            (
                "resume1.pdf",
                io.BytesIO(b"Dummy PDF content 1"),
                "application/pdf",
            ),
        ),
        (
            "files",
            (
                "resume2.docx",
                io.BytesIO(b"Dummy DOCX content 2"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        ),
        (
            "files",
            (
                "invalid.txt",
                io.BytesIO(b"bad"),
                "text/plain",
            ),
        ),
    ]

    response = await client.post(
        f"/resumes/upload/{job.id}",
        files=files,
    )

    assert response.status_code == 202

    body = response.json()

    assert body["job_id"] == job.id
    assert body["accepted_files"] == 2
    assert body["invalid_files"] == 1
    assert body["duplicate_files"] == 0
    assert body["batch_id"] > 0


@pytest.mark.asyncio
async def test_bulk_upload_rejects_content_type_extension_mismatch(client: AsyncClient, db_session):
    """A spoofed Content-Type header alone must not be enough to pass upload
    validation - the extension has to agree with it too."""
    job = Job(
        organization_id=TEST_ORG_ID,
        title="Test Spoofed Upload Job",
        description="Testing resume upload",
        job_profile={"title": "Test Spoofed Upload Job"},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    files = [
        (
            "files",
            (
                "not_really_a_pdf.exe",
                io.BytesIO(b"MZ fake binary"),
                "application/pdf",
            ),
        ),
    ]

    response = await client.post(f"/resumes/upload/{job.id}", files=files)

    assert response.status_code == 202
    body = response.json()
    assert body["accepted_files"] == 0
    assert body["invalid_files"] == 1


@pytest.mark.asyncio
async def test_bulk_upload_rejects_oversized_file(client: AsyncClient, db_session, mock_upload_io):
    job = Job(
        organization_id=TEST_ORG_ID,
        title="Test Oversized Upload Job",
        description="Testing resume upload",
        job_profile={"title": "Test Oversized Upload Job"},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    from app.core.config import settings

    oversized_content = b"x" * (settings.MAX_RESUME_FILE_SIZE_MB * 1024 * 1024 + 1)
    files = [
        (
            "files",
            ("huge.pdf", io.BytesIO(oversized_content), "application/pdf"),
        ),
    ]

    response = await client.post(f"/resumes/upload/{job.id}", files=files)

    assert response.status_code == 202
    body = response.json()
    assert body["accepted_files"] == 0
    assert body["invalid_files"] == 1


@pytest.mark.asyncio
async def test_bulk_upload_dedupes_identical_files_in_same_request(client: AsyncClient, db_session, mock_upload_io):
    """Two files with identical content uploaded in the same request must
    only create one Resume row - the second is reported as a duplicate,
    not silently dropped or double-inserted."""
    job = Job(
        organization_id=TEST_ORG_ID,
        title="Test Dedup Upload Job",
        description="Testing resume upload",
        job_profile={"title": "Test Dedup Upload Job"},
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    identical_content = b"Same resume bytes"
    files = [
        ("files", ("a.pdf", io.BytesIO(identical_content), "application/pdf")),
        ("files", ("b.pdf", io.BytesIO(identical_content), "application/pdf")),
    ]

    response = await client.post(f"/resumes/upload/{job.id}", files=files)

    assert response.status_code == 202
    body = response.json()
    assert body["accepted_files"] == 1
    assert body["duplicate_files"] == 1


async def _upload_job(db_session, title="Enqueue Job"):
    job = Job(organization_id=TEST_ORG_ID, title=title, description="Testing enqueue", job_profile={"title": title})
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


async def _resumes_of(db_session, job_id):
    from sqlalchemy import select
    from app.models.resume import Resume
    return (await db_session.execute(
        select(Resume).where(Resume.job_id == job_id).order_by(Resume.id).execution_options(populate_existing=True)
    )).scalars().all()


@pytest.mark.asyncio
async def test_bulk_upload_records_confirmed_enqueue_and_survives_enqueue_failure(client: AsyncClient, db_session, mock_upload_io):
    """A Redis failure while enqueueing must not fail the request (the
    resumes are already committed) - only confirmed enqueues are marked, so
    the recovery sweep picks up the rest."""
    _mock_save, mock_enqueue = mock_upload_io
    job = await _upload_job(db_session)
    calls = []

    async def _enqueue(resume_id, job_id, batch_id):
        calls.append(resume_id)
        if len(calls) == 2:
            raise ConnectionError("redis down")
    mock_enqueue.side_effect = _enqueue

    files = [("files", (f"r{i}.pdf", io.BytesIO(f"resume {i}".encode()), "application/pdf")) for i in range(2)]
    response = await client.post(f"/resumes/upload/{job.id}", files=files)
    assert response.status_code == 202
    assert response.json()["accepted_files"] == 2

    by_id = {r.id: r for r in await _resumes_of(db_session, job.id)}
    assert by_id[calls[0]].enqueued_at is not None
    assert by_id[calls[1]].enqueued_at is None


@pytest.mark.asyncio
async def test_bulk_upload_with_nothing_accepted_completes_its_batch(client: AsyncClient, db_session, mock_upload_io):
    from sqlalchemy import select
    from app.models.batch import ScreeningBatch
    job = await _upload_job(db_session, "Nothing Accepted")
    response = await client.post(
        f"/resumes/upload/{job.id}", files=[("files", ("x.txt", io.BytesIO(b"nope"), "text/plain"))]
    )
    batch = (await db_session.execute(
        select(ScreeningBatch).where(ScreeningBatch.id == response.json()["batch_id"])
    )).scalar_one()
    assert batch.status == "COMPLETED"


@pytest.mark.asyncio
async def test_requeue_sweep_reenqueues_only_unconfirmed_stale_uploads(db_session):
    from datetime import datetime, timedelta, timezone
    from app.models.batch import ScreeningBatch
    from app.models.resume import Resume
    from app.models.public_application import PublicApplicationSubmission
    from app.services import resume_intake

    old = datetime.now(timezone.utc) - timedelta(hours=1)
    active = await _upload_job(db_session, "Sweep Active")
    paused = await _upload_job(db_session, "Sweep Paused")
    paused.status = "PAUSED"
    batch_a = ScreeningBatch(job_id=active.id)
    batch_p = ScreeningBatch(job_id=paused.id)
    db_session.add_all([batch_a, batch_p])
    await db_session.flush()

    def _resume(job, batch, name, **kw):
        return Resume(job_id=job.id, batch_id=batch.id, filename=name, file_hash=name + str(job.id),
                      storage_key=name, status=kw.pop("status", "UPLOADED"), **kw)
    stuck = _resume(active, batch_a, "stuck", created_at=old)
    fresh = _resume(active, batch_a, "fresh")
    confirmed = _resume(active, batch_a, "confirmed", created_at=old, enqueued_at=old)
    done = _resume(active, batch_a, "done", created_at=old, status="READY")
    on_paused = _resume(paused, batch_p, "paused", created_at=old)
    public = _resume(active, batch_a, "public", created_at=old)
    db_session.add_all([stuck, fresh, confirmed, done, on_paused, public])
    await db_session.flush()
    db_session.add(PublicApplicationSubmission(
        resume_id=public.id, job_id=active.id, applicant_name="A", applicant_email="a@x.test", consent_at=old,
    ))
    await db_session.commit()

    with patch("app.services.resume_intake.queue_service.enqueue_resume", new_callable=AsyncMock) as mock_enqueue:
        requeued = await resume_intake.requeue_unenqueued_uploads()

    assert requeued == 1
    mock_enqueue.assert_awaited_once_with(stuck.id, job_id=active.id, batch_id=batch_a.id)
    refreshed = {r.filename: r for r in await _resumes_of(db_session, active.id)}
    assert refreshed["stuck"].enqueued_at is not None
    assert refreshed["fresh"].enqueued_at is None
