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