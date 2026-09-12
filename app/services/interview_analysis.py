import logging
from typing import Optional, Tuple, List, Any

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interview import Interview
from app.models.resume import Resume
from app.models.job import Job
from app.models.profile import CandidateProfile

logger = logging.getLogger(__name__)

_UNSPECIFIED_ENVELOPE = {
    "source": "unspecified",
    "workflow_run_id": None,
    "call_disposition": "unspecified",
    "gathered_context": {},
    "cost_info": {},
    "user_recording_url": None,
    "bot_recording_url": None,
}


def parse_evaluation_envelope(evaluation: Any) -> dict:
    """Defensively parse the canonical interview evaluation envelope.

    Canonical shape (populated by the Dograh webhook):
    {source, workflow_run_id, call_disposition, gathered_context, cost_info,
     user_recording_url, bot_recording_url}

    Never raises - any unrecognized/legacy/malformed shape is bucketed under
    "unspecified" rather than erroring.
    """
    if not isinstance(evaluation, dict):
        return dict(_UNSPECIFIED_ENVELOPE)

    try:
        gathered_context = evaluation.get("gathered_context")
        if not isinstance(gathered_context, dict):
            gathered_context = {}

        cost_info = evaluation.get("cost_info")
        if not isinstance(cost_info, dict):
            cost_info = {}

        source = evaluation.get("source")
        if not isinstance(source, str) or not source:
            source = "unspecified"

        call_disposition = evaluation.get("call_disposition")
        if not isinstance(call_disposition, str) or not call_disposition:
            call_disposition = "unspecified"

        return {
            "source": source,
            "workflow_run_id": evaluation.get("workflow_run_id"),
            "call_disposition": call_disposition,
            "gathered_context": gathered_context,
            "cost_info": cost_info,
            "user_recording_url": evaluation.get("user_recording_url"),
            "bot_recording_url": evaluation.get("bot_recording_url"),
        }
    except Exception:
        logger.exception("Failed to parse interview evaluation envelope; bucketing as unspecified")
        return dict(_UNSPECIFIED_ENVELOPE)


class InterviewAnalysisService:
    async def summary(self, db: AsyncSession, job_id: Optional[int] = None) -> dict:
        query = select(Interview)
        if job_id is not None:
            query = query.where(Interview.job_id == job_id)

        interviews = (await db.execute(query)).scalars().all()

        total = len(interviews)
        completed = sum(1 for i in interviews if i.status == "COMPLETED")
        completion_rate = (completed / total) if total else 0.0

        durations: List[float] = []
        disposition_breakdown: dict = {}

        for interview in interviews:
            envelope = parse_evaluation_envelope(interview.evaluation)
            disposition = envelope["call_disposition"]
            disposition_breakdown[disposition] = disposition_breakdown.get(disposition, 0) + 1

            duration = envelope["cost_info"].get("call_duration_seconds")
            if isinstance(duration, (int, float)):
                durations.append(float(duration))

        avg_duration = (sum(durations) / len(durations)) if durations else None

        return {
            "job_id": job_id,
            "total_interviews": total,
            "completed_interviews": completed,
            "completion_rate": completion_rate,
            "avg_call_duration_seconds": avg_duration,
            "disposition_breakdown": disposition_breakdown,
        }

    async def list_interviews(
        self,
        db: AsyncSession,
        job_id: Optional[int] = None,
        disposition: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[dict], int]:
        query = (
            select(
                Interview,
                Job.title.label("job_title"),
                CandidateProfile.name.label("candidate_name"),
            )
            .select_from(Interview)
            .join(Resume, Resume.id == Interview.resume_id)
            .join(Job, Job.id == Interview.job_id)
            .outerjoin(CandidateProfile, CandidateProfile.resume_id == Interview.resume_id)
        )

        if job_id is not None:
            query = query.where(Interview.job_id == job_id)

        if disposition:
            if disposition == "unspecified":
                query = query.where(
                    or_(
                        Interview.evaluation.is_(None),
                        Interview.evaluation["call_disposition"].astext.is_(None),
                    )
                )
            else:
                query = query.where(Interview.evaluation["call_disposition"].astext == disposition)

        count_query = select(func.count()).select_from(
            query.with_only_columns(Interview.id).order_by(None).subquery()
        )
        total = (await db.execute(count_query)).scalar_one()

        query = query.order_by(Interview.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        rows = (await db.execute(query)).all()

        items = []
        for row in rows:
            interview = row[0]
            envelope = parse_evaluation_envelope(interview.evaluation)
            items.append(
                {
                    "id": interview.id,
                    "job_id": interview.job_id,
                    "resume_id": interview.resume_id,
                    "status": interview.status,
                    "job_title": row.job_title,
                    "candidate_name": row.candidate_name,
                    "created_at": interview.created_at,
                    **envelope,
                }
            )

        return items, total


interview_analysis_service = InterviewAnalysisService()
