from typing import Dict, Any
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db.session import AsyncSessionLocal
from app.models.interview import Interview

class InterviewIntegrationAdapter:
    async def trigger_interview(self, candidate_id: int, job_id: int) -> bool:
        """
        Triggers an external interview (e.g. Dograh/Smartflo).
        Here we just create the persistent state tracking it as SCHEDULED.
        """
        async with AsyncSessionLocal() as session:
            try:
                # Check if it already exists
                existing = await session.execute(
                    select(Interview).where(
                        Interview.resume_id == candidate_id,
                        Interview.job_id == job_id
                    )
                )
                interview = existing.scalar_one_or_none()
                if not interview:
                    interview = Interview(
                        resume_id=candidate_id,
                        job_id=job_id,
                        status="SCHEDULED"
                    )
                    session.add(interview)
                    await session.commit()
                else:
                    interview.status = "SCHEDULED"
                    await session.commit()
                return True
            except IntegrityError:
                await session.rollback()
                # If race condition caused IntegrityError, we just return True
                return True

    async def receive_interview_status(self, candidate_id: int, job_id: int, status: str) -> bool:
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(Interview).where(
                    Interview.resume_id == candidate_id,
                    Interview.job_id == job_id
                )
            )
            interview = existing.scalar_one_or_none()
            if interview:
                interview.status = status
                await session.commit()
                return True
            return False

    async def receive_transcript(self, candidate_id: int, job_id: int, transcript: str) -> bool:
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(Interview).where(
                    Interview.resume_id == candidate_id,
                    Interview.job_id == job_id
                )
            )
            interview = existing.scalar_one_or_none()
            if interview:
                interview.transcript = transcript
                await session.commit()
                return True
            return False

    async def receive_evaluation(self, candidate_id: int, job_id: int, evaluation_data: Dict[str, Any]) -> bool:
        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(Interview).where(
                    Interview.resume_id == candidate_id,
                    Interview.job_id == job_id
                )
            )
            interview = existing.scalar_one_or_none()
            if interview:
                interview.evaluation = evaluation_data
                interview.status = "COMPLETED"
                await session.commit()
                return True
            return False

interview_adapter = InterviewIntegrationAdapter()
