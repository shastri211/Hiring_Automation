"""Organization (tenant) helpers.

Only root tables carry organization_id (jobs, candidates, users,
email_templates, app_settings, talent_pool_entries); everything else is
scoped through its root - a resume/screening result/interview/email
message through its job. Background paths (worker, outreach, email send)
derive the organization from the job of the specific row they act on.

Lookups return None (and the *_or_404 variants raise 404) for another
organization's object exactly as for a missing one, so an identifier from
another tenant is indistinguishable from one that doesn't exist.
"""
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate
from app.models.email import EmailTemplate
from app.models.job import Job
from app.models.resume import Resume
from app.models.talent_pool import TalentPoolEntry


class NotInOrganization(LookupError):
    """Raised by services when an identifier doesn't resolve inside the
    caller's organization (missing or another tenant's - deliberately the
    same error). Routes map it to 404."""


def _not_found(what: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{what} not found")


def org_job_ids(organization_id: int):
    """Subquery of this organization's job ids - the scoping predicate for
    every job-scoped table (Resume.job_id.in_(...), ScreeningResult.job_id...)."""
    return select(Job.id).where(Job.organization_id == organization_id)


async def organization_id_for_job(db: AsyncSession, job_id: int) -> Optional[int]:
    return (await db.execute(select(Job.organization_id).where(Job.id == job_id))).scalar_one_or_none()


async def get_job_for_org(db: AsyncSession, job_id: int, organization_id: int) -> Optional[Job]:
    return (
        await db.execute(select(Job).where(Job.id == job_id, Job.organization_id == organization_id))
    ).scalar_one_or_none()


async def get_job_for_org_or_404(db: AsyncSession, job_id: int, organization_id: int) -> Job:
    job = await get_job_for_org(db, job_id, organization_id)
    if job is None:
        raise _not_found("Job")
    return job


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


async def get_resume_in_org_or_404(db: AsyncSession, resume_id: int, organization_id: int) -> Resume:
    resume = await get_resume_in_org(db, resume_id, organization_id)
    if resume is None:
        raise _not_found("Resume")
    return resume


async def get_candidate_for_org(db: AsyncSession, candidate_id: int, organization_id: int) -> Optional[Candidate]:
    return (
        await db.execute(
            select(Candidate).where(Candidate.id == candidate_id, Candidate.organization_id == organization_id)
        )
    ).scalar_one_or_none()


async def get_candidate_for_org_or_404(db: AsyncSession, candidate_id: int, organization_id: int) -> Candidate:
    candidate = await get_candidate_for_org(db, candidate_id, organization_id)
    if candidate is None:
        raise _not_found("Candidate")
    return candidate


async def get_template_for_org(db: AsyncSession, template_id: int, organization_id: int) -> Optional[EmailTemplate]:
    return (
        await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.id == template_id, EmailTemplate.organization_id == organization_id
            )
        )
    ).scalar_one_or_none()


async def get_template_for_org_or_404(db: AsyncSession, template_id: int, organization_id: int) -> EmailTemplate:
    template = await get_template_for_org(db, template_id, organization_id)
    if template is None:
        raise _not_found("Template")
    return template


async def get_talent_entry_for_org_or_404(db: AsyncSession, entry_id: int, organization_id: int) -> TalentPoolEntry:
    entry = (
        await db.execute(
            select(TalentPoolEntry).where(
                TalentPoolEntry.id == entry_id, TalentPoolEntry.organization_id == organization_id
            )
        )
    ).scalar_one_or_none()
    if entry is None:
        raise _not_found("Talent pool entry")
    return entry


async def require_resumes_in_job(db: AsyncSession, job_id: int, resume_ids: Iterable[int]) -> None:
    """For request bodies listing resume ids against an (already org-checked)
    job: every id must be one of that job's resumes. Rejects the whole
    request (422) rather than silently acting on a subset, so another
    organization's ids can never be mixed into a write."""
    wanted = set(resume_ids)
    if not wanted:
        return
    found = set(
        (await db.execute(select(Resume.id).where(Resume.job_id == job_id, Resume.id.in_(wanted)))).scalars().all()
    )
    if found != wanted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": "unknown_resume_ids", "message": "One or more resumes don't belong to this job."},
        )
