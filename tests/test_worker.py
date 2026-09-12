import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.resume import Resume
from app.models.profile import CandidateProfile
from app.services.orchestrator import orchestrator
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_process_candidate_not_found():
    # Calling with invalid ID should just print and return
    await orchestrator.process_candidate(9999)
