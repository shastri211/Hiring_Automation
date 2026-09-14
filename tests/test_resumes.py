import io

import pytest
from httpx import AsyncClient

from app.models.job import Job


@pytest.mark.asyncio
async def test_bulk_upload_resumes(client: AsyncClient, db_session):
    job = Job(
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
async def test_bulk_upload_rejects_oversized_file(client: AsyncClient, db_session):
    job = Job(
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
async def test_bulk_upload_dedupes_identical_files_in_same_request(client: AsyncClient, db_session):
    """Two files with identical content uploaded in the same request must
    only create one Resume row - the second is reported as a duplicate,
    not silently dropped or double-inserted."""
    job = Job(
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