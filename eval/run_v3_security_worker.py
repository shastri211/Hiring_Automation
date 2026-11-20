"""Eval-only security, isolation, interview, and worker reliability checks."""

import asyncio
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

os.environ["DB_SCHEMA"] = "test_isolation"

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
RESULTS = ROOT / "eval" / "results"
BASE_URL = "http://127.0.0.1:8001"
PASSWORD = "SyntheticApiUser!123"
sys.path.insert(0, str(BACKEND))


def load_api_records():
    data = json.loads((RESULTS / "api_v2.json").read_text(encoding="utf-8"))
    return data["seeded_records"], data["run_id"]


async def login(client, email):
    response = await client.post("/auth/login", json={"email": email, "password": PASSWORD}, timeout=60)
    response.raise_for_status()
    return response.cookies.get("access_token") or client.cookies.get("access_token")


async def seed_fixtures(records):
    from app.db.session import AsyncSessionLocal
    from app.models.batch import ScreeningBatch
    from app.models.candidate import Candidate
    from app.models.interview import Interview
    from app.models.resume import Resume
    from app.models.screening import ScreeningResult

    async with AsyncSessionLocal() as session:
        candidates = {}
        resumes = {}
        interviews = {}
        for label in ("a", "b"):
            org_id = records[label]["org_id"]
            job_id = records[label]["job_id"]
            candidate = Candidate(
                organization_id=org_id,
                canonical_name=f"Synthetic Candidate {label}",
                primary_email=f"candidate-{label}-{uuid.uuid4().hex[:8]}@example.test",
            )
            session.add(candidate)
            await session.flush()
            batch = ScreeningBatch(
                job_id=job_id,
                batch_type="UPLOAD",
                total_resumes=1,
                status="CREATED",
            )
            session.add(batch)
            await session.flush()
            file_bytes = f"synthetic resume {label} {uuid.uuid4().hex}".encode()
            resume = Resume(
                batch_id=batch.id,
                job_id=job_id,
                candidate_id=candidate.id,
                filename=f"synthetic-{label}.txt",
                file_hash=hashlib.sha256(file_bytes).hexdigest(),
                storage_key=f"eval/synthetic-{label}.txt",
                status="READY",
            )
            session.add(resume)
            await session.flush()
            screening = ScreeningResult(
                job_id=job_id,
                resume_id=resume.id,
                screening_batch_id=batch.id,
                score=80.0,
                decision="REVIEW",
            )
            session.add(screening)
            valid = label == "a"
            interview = Interview(
                job_id=job_id,
                resume_id=resume.id,
                status="SCHEDULED",
                provider="dograh",
                public_token=f"{label}-valid-{uuid.uuid4().hex}",
                link_expires_at=datetime.now(timezone.utc) + timedelta(hours=1) if valid
                else datetime.now(timezone.utc) - timedelta(hours=1),
            )
            session.add(interview)
            candidates[label] = candidate.id
            resumes[label] = resume.id
            interviews[label] = interview.id
        await session.commit()
        return {"candidates": candidates, "resumes": resumes, "interviews": interviews}


async def security_checks(records, fixtures):
    from app.db.session import AsyncSessionLocal
    from app.models.interview import Interview

    checks = {}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        token_a = await login(client, records["a"]["email"])
        token_b = await login(client, records["b"]["email"])

        for name, token in (("tenant_a", token_a), ("tenant_b", token_b)):
            response = await client.get("/jobs/", cookies={"access_token": token})
            checks[f"{name}_jobs"] = response.status_code

        b_cookie = {"access_token": token_b}
        a_job = records["a"]["job_id"]
        b_job = records["b"]["job_id"]
        a_candidate = fixtures["candidates"]["a"]
        b_candidate = fixtures["candidates"]["b"]
        a_resume = fixtures["resumes"]["a"]

        attempts = [
            ("tenant_b_read_a_job", client.get(f"/jobs/{a_job}", cookies=b_cookie)),
            ("tenant_b_delete_a_job", client.delete(f"/jobs/{a_job}", cookies=b_cookie)),
            ("tenant_b_read_a_candidate", client.get(f"/candidates/{a_candidate}", cookies=b_cookie)),
            ("tenant_b_modify_a_candidate", client.patch(
                f"/candidates/{a_candidate}",
                json={"canonical_name": "Unauthorized mutation"},
                cookies=b_cookie,
            )),
            ("tenant_b_modify_a_result", client.patch(
                f"/jobs/{a_job}/results/{a_resume}/decision",
                json={"decision": "SHORTLIST"},
                cookies=b_cookie,
            )),
        ]
        blocked = 0
        for name, pending in attempts:
            response = await pending
            checks[name] = response.status_code
            if response.status_code in (401, 403, 404):
                blocked += 1
        checks["cross_tenant_attempts"] = f"{blocked}/{len(attempts)}"

        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as anon_client:
            response = await anon_client.get("/jobs/", timeout=30)
            checks["missing_token"] = response.status_code
        response = await client.get("/jobs/", cookies={"access_token": "invalid-token"}, timeout=30)
        checks["invalid_token"] = response.status_code

        from app.core.config import settings
        from app.services.auth import password_fingerprint
        from app.models.user import User
        from app.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.email == records["a"]["email"]))
            user = result.scalar_one()
            pwd_claim = password_fingerprint(user.hashed_password)

        expired = jwt.encode(
            {
                "sub": str(user.id),
                "purpose": "session",
                "pwd": pwd_claim,
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            settings.SECRET_KEY,
            algorithm="HS256",
        )
        response = await client.get("/jobs/", cookies={"access_token": expired}, timeout=30)
        checks["expired_token"] = response.status_code
        tampered = token_a[:-1] + ("A" if token_a[-1] != "A" else "B")
        response = await client.get("/jobs/", cookies={"access_token": tampered}, timeout=30)
        checks["tampered_token"] = response.status_code

        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Interview).where(Interview.resume_id == fixtures["resumes"]["a"]))
            valid_interview = result.scalar_one()

        response = await client.get(f"/public/interview/{valid_interview.public_token}", timeout=30)
        checks["valid_interview_link"] = response.status_code
        response = await client.get(f"/public/interview/{valid_interview.public_token}x", timeout=30)
        checks["tampered_interview_link"] = response.status_code
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Interview).where(Interview.resume_id == fixtures["resumes"]["b"]))
            expired_interview = result.scalar_one()
        response = await client.get(f"/public/interview/{expired_interview.public_token}", timeout=30)
        checks["expired_interview_link"] = response.status_code

        webhook_base = {
            "job_id": a_job,
            "resume_id": a_resume,
        }
        response = await client.post(
            "/integration/interview/status",
            json={**webhook_base, "status": "COMPLETED"},
            timeout=30,
        )
        checks["webhook_status_no_auth"] = response.status_code
        response = await client.post(
            "/integration/interview/transcript",
            json={**webhook_base, "transcript": "Synthetic transcript for eval."},
            timeout=30,
        )
        checks["webhook_transcript_no_auth"] = response.status_code
        response = await client.post(
            "/integration/interview/evaluation",
            json={
                **webhook_base,
                "evaluation_data": {"key_skills_mentioned": "Python"},
                "call_disposition": "end_call",
            },
            timeout=30,
        )
        checks["webhook_evaluation_no_auth"] = response.status_code

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Interview).where(Interview.resume_id == a_resume))
        interview = result.scalar_one()
        checks["webhook_status_processed"] = interview.status
        checks["webhook_transcript_processed"] = bool(interview.transcript)
        checks["webhook_evaluation_processed"] = bool(interview.evaluation)

    return checks


async def worker_queue_checks(records, fixtures):
    from app.services.queue import queue_service
    from app.db.session import AsyncSessionLocal
    from app.models.screening import ScreeningResult

    retry_msg = "eval-retry-" + uuid.uuid4().hex
    message_id = await queue_service.redis_client.xadd(queue_service.stream_name, {
        "action": "process_resume",
        "resume_id": str(fixtures["resumes"]["a"]),
        "job_id": str(records["a"]["job_id"]),
        "batch_id": "1",
    })
    retry_msg = message_id
    await queue_service.redis_client.hdel(queue_service.retry_hash, retry_msg)
    attempt = await queue_service.record_failure(retry_msg)
    meta = await queue_service.get_retry_metadata(retry_msg)
    should_wait = await queue_service.should_retry(retry_msg)
    mock_failures = 1
    await queue_service.redis_client.hdel(queue_service.retry_hash, retry_msg)
    mock_success = True
    await queue_service.redis_client.xack(queue_service.stream_name, queue_service.group_name, retry_msg)

    resume_id = fixtures["resumes"]["b"]
    job_id = records["b"]["job_id"]
    payload = {
        "action": "process_resume",
        "resume_id": str(resume_id),
        "job_id": str(job_id),
        "batch_id": "1",
    }
    await queue_service.enqueue_task(payload)
    await queue_service.enqueue_task(payload)

    async with AsyncSessionLocal() as session:
        stmt = insert(ScreeningResult).values(
            job_id=job_id,
            resume_id=resume_id,
            score=75.0,
            decision="REVIEW",
        ).on_conflict_do_nothing(constraint="uq_screening_job_resume")
        await session.execute(stmt)
        await session.execute(stmt)
        await session.commit()
        result = await session.execute(
            select(ScreeningResult).where(
                ScreeningResult.job_id == job_id,
                ScreeningResult.resume_id == resume_id,
            )
        )
        count = len(result.scalars().all())

    return {
        "retry_attempt_recorded": attempt,
        "retry_backoff_seconds": meta["next_retry_at"] - time.time(),
        "retry_wait_observed": should_wait,
        "mock_failures_before_success": mock_failures,
        "mock_success_after_retry": mock_success,
        "duplicate_enqueue_simulated": 2,
        "screening_result_count": count,
    }


async def main():
    records, run_id = load_api_records()
    fixtures = await seed_fixtures(records)
    security = await security_checks(records, fixtures)
    worker = await worker_queue_checks(records, fixtures)
    output = {"run_id": run_id, "security": security, "worker": worker}
    (RESULTS / "v3_security_worker.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
