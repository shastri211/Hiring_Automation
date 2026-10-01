"""Embedding-profile migration (app/services/migration.py) must embed each
candidate from the same representation first-time processing uses
(orchestrator.candidate_embedding_input) - otherwise one job's vectors mix
two kinds of text and semantic scores stop being comparable."""
import secrets
from unittest.mock import AsyncMock, patch

import pytest

from app.models.batch import ScreeningBatch
from app.models.job import Job
from app.models.profile import CandidateProfile
from app.models.resume import Resume
from app.services.migration import migration_service
from app.services.model_registry import EmbeddingProfileConfig
from tenancy_fixtures import TEST_ORG_ID

_OLD = EmbeddingProfileConfig("gemini", "gemini-embedding-2", 768, "Cosine", "resume_candidates_768", "resume_screening")
_NEW = EmbeddingProfileConfig(
    "local", "sentence-transformers/all-MiniLM-L6-v2", 384, "Cosine", "resume_candidates_local_384", "resume_screening"
)


@pytest.mark.asyncio
async def test_migration_embeds_canonical_text_like_first_time_processing(db_session):
    job = Job(organization_id=TEST_ORG_ID, title="Migrate", description="d", job_profile={"title": "Migrate"},
              embedding_profile=_OLD.model)
    db_session.add(job)
    await db_session.flush()
    batch = ScreeningBatch(job_id=job.id)
    db_session.add(batch)
    await db_session.flush()
    with_canonical = Resume(job_id=job.id, batch_id=batch.id, filename="a.pdf", file_hash=secrets.token_hex(16),
                            storage_key="a", status="READY", workflow_stage="EMBEDDED")
    without_canonical = Resume(job_id=job.id, batch_id=batch.id, filename="b.pdf", file_hash=secrets.token_hex(16),
                               storage_key="b", status="READY", workflow_stage="EMBEDDED")
    db_session.add_all([with_canonical, without_canonical])
    await db_session.flush()
    db_session.add_all([
        CandidateProfile(resume_id=with_canonical.id, name="Ann", skills=["Go"], canonical_text="Skills: Go"),
        CandidateProfile(resume_id=without_canonical.id, name="Bo", skills=["Rust"]),
    ])
    await db_session.commit()

    embedded_texts = []

    async def _embed(text, required_profile_name=None):
        embedded_texts.append(text)
        return [0.0] * _NEW.dimensions, _NEW

    with patch("app.services.migration.model_registry.get_eligible_embedding_profiles", return_value=[_OLD, _NEW]), \
         patch("app.services.migration.embedding_router.generate_embedding", side_effect=_embed), \
         patch("app.services.migration.vector_store.create_collection", new_callable=AsyncMock), \
         patch("app.services.migration.vector_store.add_points", new_callable=AsyncMock) as mock_add:
        await migration_service.migrate_job_embedding_profile(job.id)

    # First call re-embeds the job profile; then one per candidate.
    candidate_texts = embedded_texts[1:]
    assert "Skills: Go" in candidate_texts
    assert any('"skills": ["Rust"]' in t for t in candidate_texts)  # no canonical text -> JSON, as on first embed
    assert mock_add.await_args.kwargs["collection_name"] == _NEW.collection
