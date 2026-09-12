import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.models.email import EmailTemplate
from app.models.profile import CandidateProfile
from app.models.job import Job


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
async def test_queue_bulk_emails_blocks_interview_link_placeholder(mock_session_local):
    """A template requiring {{interview_link}} must be blocked with a clear error,
    since there is no real Dograh link-generation step yet."""
    from app.services.email import email_service

    mock_session = _mock_session_local(mock_session_local)

    template = MagicMock(spec=EmailTemplate)
    template.id = 1
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

    mock_session.execute = AsyncMock(
        side_effect=[template_exec, existing_exec, candidate_exec, job_exec]
    )

    mock_queue_service = MagicMock()
    mock_queue_service.enqueue_task = AsyncMock()

    with pytest.raises(ValueError, match="interview_link"):
        await email_service.queue_bulk_emails(
            job_id=1,
            resume_ids=[7],
            template_id=1,
            queue_service=mock_queue_service,
        )

    mock_queue_service.enqueue_task.assert_not_awaited()
