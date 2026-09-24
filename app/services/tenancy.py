"""Organization (tenant) helpers.

Only root tables carry organization_id (jobs, candidates, users,
email_templates, app_settings, talent_pool_entries); everything else is
scoped through its root - a resume/screening result/interview/email
message through its job. Background paths (worker, outreach, email send)
derive the organization from the job of the specific row they act on.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.resume import Resume


async def organization_id_for_job(db: AsyncSession, job_id: int) -> Optional[int]:
    return (await db.execute(select(Job.organization_id).where(Job.id == job_id))).scalar_one_or_none()


async def get_resume_in_org(db: AsyncSession, resume_id: int, organization_id: int) -> Optional[Resume]:
    """The resume, only if its job belongs to `organization_id` - None for a
    missing resume and for another organization's alike."""
    return (
        await db.execute(
            select(Resume)
            .join(Job, Job.id == Resume.job_id)
            .where(Resume.id == resume_id, Job.organization_id == organization_id)
        )
    ).scalar_one_or_none()
