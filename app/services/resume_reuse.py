"""Global file_hash reuse (Phase 3).

Text extraction, candidate structuring, and embeddings are each a pure
function of file bytes (embeddings additionally depend on the target
embedding profile/collection). When an identical file has already been
processed anywhere in the system - any job, any candidate - this module
finds that prior work so the orchestrator can copy it instead of redoing
extraction, an LLM profiling call, or an embedding API call.

Deliberately forward-looking only: resumes processed before this shipped
are not retroactively consolidated. Deliberately does not deduplicate the
physical file on disk - only the content-derived computation. And it never
touches ScreeningResult: screening is always computed fresh per
(job_id, resume_id), regardless of what was reused upstream.
"""
import logging
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import Resume
from app.services.vector_store import vector_store
from app.services.model_registry import EmbeddingProfileConfig

logger = logging.getLogger(__name__)

# Most-advanced-first: a source further along the pipeline can satisfy a
# reuse request for any earlier stage too.
_STAGE_RANK = {"EMBEDDED": 3, "PROFILED": 2, "EXTRACTED": 1}


async def find_reusable_source(db: AsyncSession, *, file_hash: str, exclude_resume_id: int) -> Optional[Resume]:
    """Best candidate to copy content-derived work from: the most-advanced
    workflow_stage among other non-failed resumes sharing this file_hash,
    tie-broken by lowest id for determinism. Byte-identical content extracts
    identically regardless of which prior run produced it, so determinism
    here is for predictability/debuggability, not correctness."""
    candidates = (
        await db.execute(
            select(Resume).where(
                Resume.file_hash == file_hash,
                Resume.id != exclude_resume_id,
                Resume.status != "FAILED",
                Resume.workflow_stage.in_(tuple(_STAGE_RANK.keys())),
            )
        )
    ).scalars().all()

    if not candidates:
        return None

    return min(candidates, key=lambda r: (-_STAGE_RANK[r.workflow_stage], r.id))


async def get_reusable_embedding(
    *, source: Resume, profile_config: EmbeddingProfileConfig
) -> Optional[List[float]]:
    """If `source` already has a point in the exact collection this job's
    embedding profile requires, returns its vector for reuse. Returns None
    if the source isn't embedded yet, or its embedding lives in a different
    collection (e.g. it was originally processed under a different job's
    embedding profile) - the caller just embeds fresh in that case."""
    if source.workflow_stage != "EMBEDDED":
        return None
    return await vector_store.get_vector(profile_config.collection, source.id)
