import pytest
from unittest.mock import patch
from app.services.interview import InterviewIntegrationAdapter

@pytest.mark.asyncio
@patch("app.services.interview.AsyncSessionLocal")
async def test_interview_adapter(mock_session_local):
    adapter = InterviewIntegrationAdapter()
    
    assert hasattr(adapter, "trigger_interview")
    assert hasattr(adapter, "receive_interview_status")
    assert hasattr(adapter, "receive_transcript")
    assert hasattr(adapter, "receive_evaluation")

