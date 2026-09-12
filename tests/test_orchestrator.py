import pytest
from app.services.orchestrator import RecruitmentOrchestrator

@pytest.mark.asyncio
async def test_orchestrator_initialization():
    orchestrator = RecruitmentOrchestrator()
    assert hasattr(orchestrator, "process_candidate")
