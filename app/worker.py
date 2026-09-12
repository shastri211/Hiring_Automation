import asyncio
import os
import uuid
import traceback
import json
from sqlalchemy import select, update, func
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.queue import queue_service
from app.models.resume import Resume
from app.models.profile import CandidateProfile
from app.models.job import Job
from app.models.batch import ScreeningBatch
from app.services.orchestrator import orchestrator
from app.services.llm_provider import ConfigurationError

WORKER_ID = settings.WORKER_ID

async def fail_task_permanently(task_type: str, item_id: int, error_msg: str):
    async with AsyncSessionLocal() as session:
        if task_type == "process_resume":
            res = await session.execute(select(Resume).where(Resume.id == item_id))
            obj = res.scalar_one_or_none()
        elif task_type == "screen_job":
            res = await session.execute(select(ScreeningBatch).where(ScreeningBatch.id == item_id))
            obj = res.scalar_one_or_none()
        elif task_type == "SEND_EMAIL":
            from app.models.email import EmailMessage
            res = await session.execute(select(EmailMessage).where(EmailMessage.id == item_id))
            obj = res.scalar_one_or_none()
        else:
            obj = None

        if obj:
            obj.status = "FAILED"
            if hasattr(obj, "error_message"):
                obj.error_message = f"Max retries exceeded. Last error: {error_msg}"
                
            if hasattr(obj, "batch_id") and obj.batch_id:
                from sqlalchemy import func
                count_res = await session.execute(
                    select(func.count(Resume.id)).where(
                        Resume.batch_id == obj.batch_id,
                        Resume.status.in_(["READY", "FAILED"])
                    )
                )
                completed_count = count_res.scalar_one()

                batch_res = await session.execute(
                    select(ScreeningBatch).where(ScreeningBatch.id == obj.batch_id)
                )
                batch = batch_res.scalar_one_or_none()

                if batch and completed_count >= batch.total_resumes:
                    batch.status = "COMPLETED"
                
            await session.commit()


async def recover_stuck_messages():
    while True:
        try:
            # Claim them for one of our actual consumers that calls consume()
            actual_consumer = f"{WORKER_ID}-0"
            claimed = await queue_service.claim_stuck_messages(actual_consumer, min_idle_ms=300000)
            for c_msg_id, payload in claimed:
                print(f"Worker {actual_consumer} recovered stuck message {c_msg_id}")
        except Exception as e:
            print(f"Recovery task error: {e}")
        await asyncio.sleep(60)


import logging
logger = logging.getLogger(__name__)

async def worker_loop(consumer_id: str):
    logger.info(f"Worker {consumer_id} started. Waiting for jobs...")

    while True:
        try:
            messages = await queue_service.consume(consumer_id, count=1, block_ms=5000)

            for msg_id, payload in messages:
                action = payload.get("action") or payload.get("type") or payload.get("task_type")

                if action == "process_resume":
                    item_id = int(payload.get("resume_id", 0))
                elif action == "screen_job":
                    item_id = int(payload.get("batch_id", 0))
                elif action == "migrate_job":
                    item_id = int(payload.get("job_id", 0))
                elif action == "SEND_EMAIL":
                    item_id = int(payload.get("email_message_id", 0))
                else:
                    item_id = 0

                if not await queue_service.should_retry(msg_id):
                    if await queue_service.is_exhausted(msg_id):
                        logger.error(f"Message {msg_id} exceeded max retries. Failing permanently.")
                        await fail_task_permanently(action, item_id, "Max retries exceeded")
                        await queue_service.ack(msg_id)
                    else:
                        await asyncio.sleep(1)
                    continue

                try:
                    if action == "process_resume":
                        logger.info(f"Processing candidate {item_id} (msg_id: {msg_id})")
                        await orchestrator.process_candidate(item_id)
                    elif action == "screen_job":
                        job_id = int(payload.get("job_id", 0))
                        logger.info(f"Screening job {job_id} for batch {item_id}")
                        from app.services.screener import screener_service
                        async with AsyncSessionLocal() as session:
                            job_res = await session.execute(select(Job).where(Job.id == job_id))
                            job = job_res.scalar_one_or_none()
                            if job and job.status == "ACTIVE":
                                await screener_service.screen_job(session, job)
                                if item_id:
                                    batch_res = await session.execute(select(ScreeningBatch).where(ScreeningBatch.id == item_id))
                                    batch = batch_res.scalar_one_or_none()
                                    if batch:
                                        batch.status = "COMPLETED"
                                        await session.commit()
                            else:
                                logger.info(f"Skipping screening for job {job_id} (status: {job.status if job else 'DELETED'})")
                                # Consider batch completed if skipping? Let's just drop it.
                                if item_id:
                                    batch_res = await session.execute(select(ScreeningBatch).where(ScreeningBatch.id == item_id))
                                    batch = batch_res.scalar_one_or_none()
                                    if batch:
                                        batch.status = "COMPLETED"
                                        await session.commit()
                    elif action == "migrate_job":
                        job_id = int(payload.get("job_id", 0))
                        logger.info(f"Migrating embedding profile for job {job_id}")
                        from app.services.migration import migration_service
                        await migration_service.migrate_job_embedding_profile(job_id)
                    elif action == "SEND_EMAIL":
                        logger.info(f"Sending email for message {item_id}")
                        from app.services.email import email_service
                        await email_service.process_send_email_task(item_id)

                    await queue_service.ack(msg_id)
                except ConfigurationError as e:
                    logger.error(f"Configuration error: {e}. Failing permanently.")
                    await fail_task_permanently(action, item_id, str(e))
                    await queue_service.ack(msg_id)
                except Exception as e:
                    attempt = await queue_service.record_failure(msg_id)
                    logger.exception(f"Task {action} on {item_id} failed (Attempt {attempt}). Not acking message {msg_id}.")

        except Exception as e:
            logger.exception(f"Worker Loop Error: {e}")
            await asyncio.sleep(5)


async def main():
    await queue_service.init_stream()
    tasks = [asyncio.create_task(worker_loop(f"{WORKER_ID}-{i}")) for i in range(settings.WORKER_CONCURRENCY)]
    tasks.append(asyncio.create_task(recover_stuck_messages()))
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())




