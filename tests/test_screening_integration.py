import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_create_job_and_screen(db_session, test_client):
    from unittest.mock import patch
    
    with patch('app.api.jobs.profiler_service.profile_job') as mock_profile, \
         patch('app.api.jobs.embedding_router.generate_embedding') as mock_embed, \
         patch('app.api.jobs.queue_service.enqueue_task') as mock_enqueue:
         
        mock_profile.return_value = {"title": "Test Engineer", "required_skills": ["Python"]}
        mock_embed.return_value = [0.1, 0.2]
        mock_enqueue.return_value = None
        
        # 1. Create Job
        response = await test_client.post(
            "/jobs/",
            json={"title": "Test Job", "description": "Need Python dev"}
        )
        assert response.status_code == 201
        job_data = response.json()
        job_id = job_data["id"]
        
        # 2. Trigger Screening
        response = await test_client.post(f"/jobs/{job_id}/screen")
        assert response.status_code == 202
        assert "batch_id" in response.json()
        
        mock_enqueue.assert_called_once()
