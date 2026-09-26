import secrets

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.job import Job
from app.models.resume import Resume
from app.models.batch import ScreeningBatch
from app.services.orchestrator import orchestrator
from app.services.screener import screener_service
from app.core.config import settings
from app.services.embeddings import embedding_router
from tenancy_fixtures import TEST_ORG_ID


@pytest.mark.asyncio
async def test_process_candidate_stops_at_embedded(db_session):
    # Verifies that process_candidate ends at EMBEDDED/READY
    # and does not perform candidate analysis or shortlisting.

    with patch(
        "app.services.orchestrator.get_extractor",
    ) as mock_get_extractor, patch(
        "app.services.orchestrator.LocalProfilerService.profile_candidate",
    ) as mock_local_cp, patch(
        "app.services.orchestrator.profiler_service.profile_candidate",
        new_callable=AsyncMock,
    ) as mock_cp, patch(
        "app.services.orchestrator.embedding_router.generate_embedding",
        new_callable=AsyncMock,
    ) as mock_sm_embed, patch(
        "app.services.orchestrator.vector_store.create_collection",
        new_callable=AsyncMock,
    ) as mock_sm_create, patch(
        "app.services.orchestrator.vector_store.add_points",
        new_callable=AsyncMock,
    ) as mock_sm_add:

        mock_extractor = AsyncMock()
        mock_extractor.extract.return_value = "Test Text"
        mock_get_extractor.return_value = mock_extractor

        mock_local_cp.return_value = (None, None, {"is_insufficient": True})

        mock_cp.return_value = {
            "name": "Test Profile",
            "summary": "Test summary",
            "total_experience_years": 2.0,
        }

        mock_sm_embed.return_value = ([0.1, 0.2], MagicMock(collection="test", dimensions=2))

        job = Job(
        organization_id=TEST_ORG_ID,
            title="Test",
            description="Test",
            job_profile={"title": "Test Job"},
        )
        db_session.add(job)
        await db_session.flush()

        batch = ScreeningBatch(
            job_id=job.id,
            status="PROCESSING",
            total_resumes=1,
            processed=0,
            failed=0,
        )
        db_session.add(batch)
        await db_session.flush()

        resume = Resume(
            job_id=job.id,
            batch_id=batch.id,
            filename="test.pdf",
            file_hash=f"testhash_{secrets.token_hex(8)}",
            storage_key="testkey",
            workflow_stage="UPLOADED",
            status="PROCESSING",
        )
        db_session.add(resume)
        await db_session.commit()

        await orchestrator.process_candidate(resume.id)

        await db_session.refresh(resume)
        await db_session.refresh(batch)

        assert resume.workflow_stage == "EMBEDDED"
        assert resume.status == "READY"
        assert batch.processed == 1

        mock_extractor.extract.assert_called_once()
        mock_cp.assert_called_once()
        mock_sm_embed.assert_called_once()
        mock_sm_add.assert_called_once()


@pytest.mark.asyncio
async def test_screen_job_filters_by_job_id(db_session):
    # Verifies that screen_job passes the correct job_id filter
    # to Qdrant without calling a real embedding provider.

    job = Job(
        organization_id=TEST_ORG_ID,
        title="Test Job",
        description="Desc",
        job_profile={"title": "Dev"},
    )
    db_session.add(job)
    await db_session.flush()

    batch = ScreeningBatch(
        job_id=job.id,
        status="COMPLETED",
        total_resumes=1,
    )
    db_session.add(batch)
    await db_session.flush()

    resume = Resume(
        job_id=job.id,
        batch_id=batch.id,
        filename="test.pdf",
        file_hash=f"testhash_{secrets.token_hex(8)}",
        storage_key="testkey",
        status="READY",
        workflow_stage="EMBEDDED",
    )
    db_session.add(resume)
    await db_session.commit()

    with patch(
        "app.services.screener.vector_store.search",
        new_callable=AsyncMock,
    ) as mock_search, patch(
        "app.services.screener.ScreenerService.evaluate_candidate",
        new_callable=AsyncMock,
    ) as mock_eval, patch.object(
        embedding_router,
        "generate_embedding",
        new_callable=AsyncMock,
    ) as mock_embedding, patch(
        # This test uses the real db_session, and job/resume below are real
        # committed rows - a SHORTLIST result now fires outreach automation
        # (see ScreenerService.screen_job), which would otherwise create a
        # real Interview row against them via an unmocked AsyncSessionLocal().
        "app.services.outreach.outreach_service.on_decision_shortlisted",
        new_callable=AsyncMock,
    ):

        mock_profile = MagicMock()
        mock_embedding.return_value = (
            [0.1] * settings.EMBEDDING_DIMENSION,
            mock_profile
        )

        mock_search.return_value = [
            (
                "uuid",
                0.9,
                {
                    "resume_id": resume.id,
                    "job_id": job.id,
                    "profile": {
                        "skills": ["Python"],
                    },
                },
            )
        ]

        mock_eval.return_value = {
            "score": 85.0,
            "strengths": ["Python"],
            "gaps": [],
            "evidence": [],
            "decision": "SHORTLIST",
        }

        results = await screener_service.screen_job(
            db_session,
            job,
        )

        mock_embedding.assert_called_once()

        mock_search.assert_called_once()

        kwargs = mock_search.call_args.kwargs

        assert kwargs["query_filter"] == {
            "job_id": job.id,
        }

        assert kwargs["query_vector"] == [0.1] * settings.EMBEDDING_DIMENSION

        assert len(results) == 1
        assert results[0].decision == "SHORTLIST"
        assert results[0].resume_id == resume.id
        assert results[0].job_id == job.id

        mock_eval.assert_called_once()

@pytest.mark.asyncio
async def test_lazy_enrichment_never_sends_pii_to_evaluation(db_session):
    """A LOCAL profile enriched by the LLM during screening must be
    sanitized before it reaches the evaluation prompt - the enrichment
    result carries name/contact, which evaluation must never see."""
    from app.models.profile import CandidateProfile
    from app.services.profiler import profiler_service

    job = Job(organization_id=TEST_ORG_ID, title="Dev", description="Desc", job_profile={"title": "Dev"})
    db_session.add(job)
    await db_session.flush()
    batch = ScreeningBatch(job_id=job.id, status="COMPLETED", total_resumes=1)
    db_session.add(batch)
    await db_session.flush()
    resume = Resume(
        job_id=job.id, batch_id=batch.id, filename="r.pdf",
        file_hash=f"testhash_{secrets.token_hex(8)}", storage_key="k",
        status="READY", workflow_stage="EMBEDDED", extracted_text="Jane Doe jane@example.com Python",
    )
    db_session.add(resume)
    await db_session.flush()
    db_session.add(CandidateProfile(resume_id=resume.id, name="Jane Doe", skills=["Python"], extraction_method="LOCAL"))
    await db_session.commit()

    enriched = {
        "name": "Jane Doe",
        "contact": {"email": "jane@example.com", "phone": "555-0100"},
        "skills": ["Python", "FastAPI"],
    }
    with patch("app.services.screener.vector_store.search", new_callable=AsyncMock) as mock_search, \
         patch("app.services.screener.ScreenerService.evaluate_candidate", new_callable=AsyncMock) as mock_eval, \
         patch.object(embedding_router, "generate_embedding", new_callable=AsyncMock) as mock_embedding, \
         patch.object(profiler_service, "profile_candidate", new_callable=AsyncMock, return_value=enriched):
        mock_embedding.return_value = ([0.1] * settings.EMBEDDING_DIMENSION, MagicMock())
        mock_search.return_value = [
            ("1", 0.9, {"resume_id": resume.id, "job_id": job.id, "profile": {"name": "Jane Doe", "skills": ["Python"]}})
        ]
        mock_eval.return_value = {"score": 60.0, "strengths": [], "gaps": [], "evidence": [], "decision": "REVIEW"}

        await screener_service.screen_job(db_session, job)

    evaluated_profile = mock_eval.call_args.args[1]
    assert evaluated_profile["skills"] == ["Python", "FastAPI"]
    for pii_field in ("name", "contact", "email", "phone"):
        assert pii_field not in evaluated_profile


@pytest.mark.asyncio
async def test_screen_job_links_results_to_its_screening_batch(db_session):
    job = Job(organization_id=TEST_ORG_ID, title="Dev", description="Desc", job_profile={"title": "Dev"})
    db_session.add(job)
    await db_session.flush()
    upload = ScreeningBatch(job_id=job.id, status="COMPLETED", total_resumes=1)
    screen = ScreeningBatch(job_id=job.id, status="PROCESSING", total_resumes=1, batch_type="SCREEN")
    db_session.add_all([upload, screen])
    await db_session.flush()
    resume = Resume(
        job_id=job.id, batch_id=upload.id, filename="r.pdf",
        file_hash=f"testhash_{secrets.token_hex(8)}", storage_key="k", status="READY", workflow_stage="EMBEDDED",
    )
    db_session.add(resume)
    await db_session.commit()

    with patch("app.services.screener.vector_store.search", new_callable=AsyncMock) as mock_search, \
         patch("app.services.screener.ScreenerService.evaluate_candidate", new_callable=AsyncMock) as mock_eval, \
         patch.object(embedding_router, "generate_embedding", new_callable=AsyncMock) as mock_embedding:
        mock_embedding.return_value = ([0.1] * settings.EMBEDDING_DIMENSION, MagicMock())
        mock_search.return_value = [("1", 0.9, {"resume_id": resume.id, "job_id": job.id, "profile": {"skills": ["Python"]}})]
        mock_eval.return_value = {"score": 60.0, "strengths": [], "gaps": [], "evidence": [], "decision": "REVIEW"}

        results = await screener_service.screen_job(db_session, job, screening_batch_id=screen.id)

    assert [r.screening_batch_id for r in results] == [screen.id]
