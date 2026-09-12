import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient

from app.models.email import EmailTemplate
from app.models.profile import CandidateProfile
from app.models.job import Job
from app.models.settings import AppSettings


def _mock_session_local(mock_session_local):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session
    return mock_session


@pytest.mark.asyncio
@patch("app.services.email.AsyncSessionLocal", new_callable=MagicMock)
async def test_queue_bulk_emails_enqueues_via_shared_queue_service(mock_session_local):
    """queue_bulk_emails must push a flat {'action': 'SEND_EMAIL', ...} payload onto
    the shared queue_service (the same contract every other producer uses), not a
    hand-rolled redis_client.xadd call on a different stream/shape."""
    from app.services.email import email_service

    mock_session = _mock_session_local(mock_session_local)

    template = MagicMock(spec=EmailTemplate)
    template.id = 1
    template.body_content = "Hi {{candidate_name}}, thanks for applying to {{job_title}}."
    template_exec = MagicMock()
    template_exec.scalar_one_or_none.return_value = template

    existing_exec = MagicMock()
    existing_exec.scalar_one_or_none.return_value = None

    candidate = MagicMock(spec=CandidateProfile)
    candidate.email = "jane@example.com"
    candidate.name = "Jane Doe"
    candidate_exec = MagicMock()
    candidate_exec.scalar_one_or_none.return_value = candidate

    job = MagicMock(spec=Job)
    job.title = "Backend Engineer"
    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = job

    mock_session.execute = AsyncMock(
        side_effect=[template_exec, existing_exec, candidate_exec, job_exec]
    )

    new_msg = MagicMock()
    new_msg.id = 42

    def _add(obj):
        obj.id = 42

    mock_session.add = MagicMock(side_effect=_add)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_queue_service = MagicMock()
    mock_queue_service.enqueue_task = AsyncMock()

    queued_count = await email_service.queue_bulk_emails(
        job_id=1,
        resume_ids=[7],
        template_id=1,
        queue_service=mock_queue_service,
    )

    assert queued_count == 1
    mock_queue_service.enqueue_task.assert_awaited_once_with(
        {"action": "SEND_EMAIL", "email_message_id": 42}
    )


@pytest.mark.asyncio
@patch("app.services.email.AsyncSessionLocal", new_callable=MagicMock)
async def test_queue_bulk_emails_skips_candidate_without_interview_link(mock_session_local):
    """A template requiring {{interview_link}} but with no Interview/public_token
    yet for this (job_id, resume_id) must skip only that candidate (log +
    continue) rather than blocking the whole batch or raising."""
    from app.services.email import email_service

    mock_session = _mock_session_local(mock_session_local)

    template = MagicMock(spec=EmailTemplate)
    template.id = 1
    template.subject = "Interview"
    template.body_content = "Book your interview: {{interview_link}}"
    template_exec = MagicMock()
    template_exec.scalar_one_or_none.return_value = template

    existing_exec = MagicMock()
    existing_exec.scalar_one_or_none.return_value = None

    candidate = MagicMock(spec=CandidateProfile)
    candidate.email = "jane@example.com"
    candidate.name = "Jane Doe"
    candidate_exec = MagicMock()
    candidate_exec.scalar_one_or_none.return_value = candidate

    job = MagicMock(spec=Job)
    job.title = "Backend Engineer"
    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = job

    interview_exec = MagicMock()
    interview_exec.scalar_one_or_none.return_value = None  # no Interview row yet

    mock_session.execute = AsyncMock(
        side_effect=[template_exec, existing_exec, candidate_exec, job_exec, interview_exec]
    )

    mock_queue_service = MagicMock()
    mock_queue_service.enqueue_task = AsyncMock()

    queued_count = await email_service.queue_bulk_emails(
        job_id=1,
        resume_ids=[7],
        template_id=1,
        queue_service=mock_queue_service,
    )

    assert queued_count == 0
    mock_queue_service.enqueue_task.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.services.email.AsyncSessionLocal", new_callable=MagicMock)
@patch("app.services.email.settings.PUBLIC_APP_BASE_URL", "https://app.example.com")
async def test_queue_bulk_emails_renders_interview_link_when_present(mock_session_local):
    """Once trigger_interview has minted a public_token, {{interview_link}}
    must render to the real candidate-facing URL."""
    from app.services.email import email_service
    import datetime as dt

    mock_session = _mock_session_local(mock_session_local)

    template = MagicMock(spec=EmailTemplate)
    template.id = 1
    template.subject = "Interview"
    template.body_content = "Book your interview: {{interview_link}}"
    template_exec = MagicMock()
    template_exec.scalar_one_or_none.return_value = template

    existing_exec = MagicMock()
    existing_exec.scalar_one_or_none.return_value = None

    candidate = MagicMock(spec=CandidateProfile)
    candidate.email = "jane@example.com"
    candidate.name = "Jane Doe"
    candidate_exec = MagicMock()
    candidate_exec.scalar_one_or_none.return_value = candidate

    job = MagicMock(spec=Job)
    job.title = "Backend Engineer"
    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = job

    interview = MagicMock()
    interview.public_token = "tok_abc123"
    interview.link_expires_at = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
    interview_exec = MagicMock()
    interview_exec.scalar_one_or_none.return_value = interview

    mock_session.execute = AsyncMock(
        side_effect=[template_exec, existing_exec, candidate_exec, job_exec, interview_exec]
    )

    new_msg = MagicMock()

    def _add(obj):
        obj.id = 99

    mock_session.add = MagicMock(side_effect=_add)
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_queue_service = MagicMock()
    mock_queue_service.enqueue_task = AsyncMock()

    queued_count = await email_service.queue_bulk_emails(
        job_id=1,
        resume_ids=[7],
        template_id=1,
        queue_service=mock_queue_service,
    )

    assert queued_count == 1
    mock_queue_service.enqueue_task.assert_awaited_once_with(
        {"action": "SEND_EMAIL", "email_message_id": 99}
    )
    # Assert the rendered body contains the real, fully-built URL.
    added_msg = mock_session.add.call_args[0][0]
    assert added_msg.body_content == "Book your interview: https://app.example.com/interview-room/tok_abc123"


@pytest.mark.asyncio
@patch("app.services.email.AsyncSessionLocal", new_callable=MagicMock)
async def test_queue_bulk_emails_skips_when_link_expired(mock_session_local):
    """An expired interview link must never be emailed - skip rather than
    rendering a dead link."""
    from app.services.email import email_service
    import datetime as dt

    mock_session = _mock_session_local(mock_session_local)

    template = MagicMock(spec=EmailTemplate)
    template.id = 1
    template.subject = "Interview"
    template.body_content = "Book your interview: {{interview_link}}"
    template_exec = MagicMock()
    template_exec.scalar_one_or_none.return_value = template

    existing_exec = MagicMock()
    existing_exec.scalar_one_or_none.return_value = None

    candidate = MagicMock(spec=CandidateProfile)
    candidate.email = "jane@example.com"
    candidate.name = "Jane Doe"
    candidate_exec = MagicMock()
    candidate_exec.scalar_one_or_none.return_value = candidate

    job = MagicMock(spec=Job)
    job.title = "Backend Engineer"
    job_exec = MagicMock()
    job_exec.scalar_one_or_none.return_value = job

    interview = MagicMock()
    interview.public_token = "tok_abc123"
    interview.link_expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
    interview_exec = MagicMock()
    interview_exec.scalar_one_or_none.return_value = interview

    mock_session.execute = AsyncMock(
        side_effect=[template_exec, existing_exec, candidate_exec, job_exec, interview_exec]
    )

    mock_queue_service = MagicMock()
    mock_queue_service.enqueue_task = AsyncMock()

    with patch("app.services.email.settings.PUBLIC_APP_BASE_URL", "https://app.example.com"):
        queued_count = await email_service.queue_bulk_emails(
            job_id=1,
            resume_ids=[7],
            template_id=1,
            queue_service=mock_queue_service,
        )

    assert queued_count == 0
    mock_queue_service.enqueue_task.assert_not_awaited()


# -- A8: template PATCH / DELETE, and global messages list ---------------------

def _make_template(id=1, name="Welcome", subject="Hi", body_content="Body"):
    t = MagicMock(spec=EmailTemplate)
    t.id = id
    t.name = name
    t.subject = subject
    t.body_content = body_content
    import datetime
    t.created_at = datetime.datetime.utcnow()
    t.updated_at = None
    return t


@pytest.mark.asyncio
async def test_update_template_success(client: AsyncClient):
    from app.api import emails as emails_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[emails_api.get_db] = mock_get_db

    template = _make_template()
    find_exec = MagicMock()
    find_exec.scalar_one_or_none.return_value = template

    mock_db.execute = AsyncMock(return_value=find_exec)
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    try:
        response = await client.patch("/emails/templates/1", json={"subject": "Updated subject"})
        assert response.status_code == 200
        assert response.json()["subject"] == "Updated subject"
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_template_not_found(client: AsyncClient):
    from app.api import emails as emails_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[emails_api.get_db] = mock_get_db

    missing_exec = MagicMock()
    missing_exec.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=missing_exec)

    try:
        response = await client.patch("/emails/templates/999", json={"subject": "x"})
        assert response.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_update_template_name_collision(client: AsyncClient):
    from app.api import emails as emails_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[emails_api.get_db] = mock_get_db

    template = _make_template(id=1, name="Welcome")
    find_exec = MagicMock()
    find_exec.scalar_one_or_none.return_value = template

    collision_exec = MagicMock()
    collision_exec.scalar_one_or_none.return_value = _make_template(id=2, name="Rejection")

    mock_db.execute = AsyncMock(side_effect=[find_exec, collision_exec])

    try:
        response = await client.patch("/emails/templates/1", json={"name": "Rejection"})
        assert response.status_code == 400
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_template_nulls_out_references_before_deleting(client: AsyncClient):
    from app.api import emails as emails_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[emails_api.get_db] = mock_get_db

    template = _make_template(id=1)
    find_exec = MagicMock()
    find_exec.scalar_one_or_none.return_value = template

    mock_db.execute = AsyncMock(side_effect=[find_exec, MagicMock(), MagicMock(), MagicMock()])
    mock_db.delete = AsyncMock()
    mock_db.commit = AsyncMock()

    try:
        response = await client.delete("/emails/templates/1")
        assert response.status_code == 204
        # find template + null EmailMessage.template_id + null both AppSettings FKs = 4 calls
        assert mock_db.execute.await_count == 4
        mock_db.delete.assert_called_once_with(template)
        mock_db.commit.assert_called_once()
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_template_not_found(client: AsyncClient):
    from app.api import emails as emails_api
    from app.main import app as fastapi_app

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[emails_api.get_db] = mock_get_db

    missing_exec = MagicMock()
    missing_exec.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=missing_exec)

    try:
        response = await client.delete("/emails/templates/999")
        assert response.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_list_email_messages_paginated(client: AsyncClient):
    from app.api import emails as emails_api
    from app.main import app as fastapi_app
    from app.models.email import EmailMessage
    import datetime

    mock_db = AsyncMock()

    async def mock_get_db():
        yield mock_db

    fastapi_app.dependency_overrides[emails_api.get_db] = mock_get_db

    msg = MagicMock(spec=EmailMessage)
    msg.id = 1
    msg.job_id = 1
    msg.resume_id = 7
    msg.template_id = 1
    msg.subject = "Hi"
    msg.body_content = "Body"
    msg.status = "SENT"
    msg.provider_message_id = "abc"
    msg.error_message = None
    msg.created_at = datetime.datetime.utcnow()
    msg.sent_at = datetime.datetime.utcnow()

    count_exec = MagicMock()
    count_exec.scalar_one.return_value = 1

    rows_exec = MagicMock()
    rows_exec.scalars.return_value.all.return_value = [msg]

    summary_exec = MagicMock()
    summary_exec.all.return_value = []

    mock_db.execute = AsyncMock(side_effect=[count_exec, rows_exec, summary_exec])

    try:
        response = await client.get("/emails/messages?status=SENT")
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["resume_id"] == 7
        assert body["items"][0]["status"] == "SENT"
    finally:
        fastapi_app.dependency_overrides.clear()
