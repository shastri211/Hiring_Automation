from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resume import Resume
from app.models.job import Job
from app.models.screening import ScreeningResult
from app.models.interview import Interview


class AnalyticsService:
    async def funnel(self, db: AsyncSession, job_id: Optional[int] = None) -> dict:
        query = (
            select(
                func.count(func.distinct(Resume.id)).label("uploaded"),
                func.count(
                    func.distinct(case((Resume.status.in_(["READY", "FAILED"]), Resume.id)))
                ).label("processed"),
                func.count(func.distinct(ScreeningResult.id)).label("screened"),
                func.count(
                    func.distinct(case((ScreeningResult.decision == "SHORTLIST", ScreeningResult.id)))
                ).label("shortlisted"),
                func.count(func.distinct(Interview.id)).label("interviewed"),
                func.count(
                    func.distinct(case((Interview.status == "COMPLETED", Interview.id)))
                ).label("completed"),
            )
            .select_from(Resume)
            .outerjoin(
                ScreeningResult,
                (ScreeningResult.resume_id == Resume.id) & (ScreeningResult.job_id == Resume.job_id),
            )
            .outerjoin(
                Interview,
                (Interview.resume_id == Resume.id) & (Interview.job_id == Resume.job_id),
            )
        )
        if job_id is not None:
            query = query.where(Resume.job_id == job_id)

        row = (await db.execute(query)).one()
        return {
            "job_id": job_id,
            "uploaded": row.uploaded or 0,
            "processed": row.processed or 0,
            "screened": row.screened or 0,
            "shortlisted": row.shortlisted or 0,
            "interviewed": row.interviewed or 0,
            "completed": row.completed or 0,
        }

    async def decision_breakdown(self, db: AsyncSession, job_id: Optional[int] = None) -> dict:
        query = select(ScreeningResult.decision, func.count(ScreeningResult.id)).group_by(
            ScreeningResult.decision
        )
        if job_id is not None:
            query = query.where(ScreeningResult.job_id == job_id)

        rows = (await db.execute(query)).all()
        items = [{"decision": decision, "count": count} for decision, count in rows]
        total = sum(item["count"] for item in items)
        return {"items": items, "total": total}

    async def throughput(
        self, db: AsyncSession, days: int = 30, job_id: Optional[int] = None
    ) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = (
            select(
                func.date_trunc("day", ScreeningResult.created_at).label("day"),
                func.count(ScreeningResult.id),
            )
            .where(ScreeningResult.created_at >= cutoff)
            .group_by("day")
            .order_by("day")
        )
        if job_id is not None:
            query = query.where(ScreeningResult.job_id == job_id)

        rows = (await db.execute(query)).all()
        counts_by_date = {row[0].date(): row[1] for row in rows if row[0] is not None}

        items = []
        today = datetime.now(timezone.utc).date()
        for offset in range(days - 1, -1, -1):
            d = today - timedelta(days=offset)
            items.append({"date": d, "count": counts_by_date.get(d, 0)})

        return {"items": items}

    async def time_in_stage(self, db: AsyncSession, job_id: Optional[int] = None) -> dict:
        resume_to_screened_query = (
            select(func.avg(func.extract("epoch", ScreeningResult.created_at - Resume.created_at)))
            .select_from(ScreeningResult)
            .join(Resume, Resume.id == ScreeningResult.resume_id)
        )
        screened_to_interview_query = (
            select(func.avg(func.extract("epoch", Interview.created_at - ScreeningResult.created_at)))
            .select_from(Interview)
            .join(
                ScreeningResult,
                (ScreeningResult.resume_id == Interview.resume_id)
                & (ScreeningResult.job_id == Interview.job_id),
            )
        )
        if job_id is not None:
            resume_to_screened_query = resume_to_screened_query.where(ScreeningResult.job_id == job_id)
            screened_to_interview_query = screened_to_interview_query.where(Interview.job_id == job_id)

        resume_to_screened = (await db.execute(resume_to_screened_query)).scalar_one_or_none()
        screened_to_interview = (await db.execute(screened_to_interview_query)).scalar_one_or_none()

        return {
            "resume_to_screened_seconds_approx": float(resume_to_screened)
            if resume_to_screened is not None
            else None,
            "screened_to_interview_seconds_approx": float(screened_to_interview)
            if screened_to_interview is not None
            else None,
        }

    async def job_volume(self, db: AsyncSession) -> dict:
        query = (
            select(Job.id, Job.title, func.count(Resume.id))
            .select_from(Job)
            .outerjoin(Resume, Resume.job_id == Job.id)
            .group_by(Job.id, Job.title)
            .order_by(Job.id)
        )
        rows = (await db.execute(query)).all()
        items = [
            {"job_id": job_id, "job_title": title, "resume_count": count}
            for job_id, title, count in rows
        ]
        return {"items": items}


analytics_service = AnalyticsService()
