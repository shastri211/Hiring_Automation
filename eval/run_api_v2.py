"""Preflight, seed synthetic tenants, and run authenticated API/security checks.

No Docker or application-code changes are used. Logins are sequential and
tokens are reused by all benchmark workers.
"""
import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx

os.environ["DB_SCHEMA"] = "test_isolation"

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
BASE_URL = "http://127.0.0.1:8001"


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    return round(values[min(len(values) - 1, int(len(values) * p / 100 + 0.999) - 1)], 3)


async def seed():
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from sqlalchemy import select
    from app.db.session import AsyncSessionLocal
    from app.models.job import Job
    from app.models.organization import Organization
    from app.models.user import User
    from app.services.auth import hash_password

    run_id = uuid.uuid4().hex[:12]
    password = "SyntheticApiUser!123"
    records = {}
    async with AsyncSessionLocal() as session:
        for label in ("a", "b"):
            org = Organization(name=f"API Tenant {label} {run_id}")
            session.add(org)
            await session.flush()
            user = User(
                organization_id=org.id,
                email=f"api-{label}-{run_id}@example.test",
                hashed_password=hash_password(password),
                name=f"API User {label}",
                role="admin",
                is_active=True,
                email_verified_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            )
            job = Job(
                organization_id=org.id,
                title=f"API Tenant {label} Job",
                description="Synthetic API load-test job",
                job_profile={"role_summary": "Synthetic API test", "required_skills": ["Python"]},
                status="ACTIVE",
            )
            session.add_all([user, job])
            await session.flush()
            records[label] = {"org_id": org.id, "user_id": user.id, "job_id": job.id, "email": user.email}
        await session.commit()
    return run_id, password, records


async def login(client, email, password):
    response = await client.post("/auth/login", json={"email": email, "password": password}, timeout=60)
    response.raise_for_status()
    return response.cookies.get("access_token") or client.cookies.get("access_token")


async def preflight():
    failures = []
    sys.path.insert(0, str(ROOT / "backend"))
    from app.core.config import settings

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code != 200:
                failures.append(f"backend /health status={response.status_code}")
        except Exception as exc:
            failures.append(f"backend unavailable: {type(exc).__name__}: {exc}")
        try:
            import redis.asyncio as redis
            r = redis.from_url("redis://127.0.0.1:6379/0")
            ping = await r.ping()
            await r.aclose()
            if ping is not True:
                failures.append(f"Redis PING={ping}")
        except Exception as exc:
            failures.append(f"Redis unavailable: {type(exc).__name__}: {exc}")
        try:
            headers = {"api-key": settings.QDRANT_API_KEY} if settings.QDRANT_API_KEY else {}
            response = await client.get(f"{settings.QDRANT_URL.rstrip('/')}/collections", headers=headers)
            if response.status_code != 200:
                failures.append(f"Qdrant status={response.status_code}")
        except Exception as exc:
            failures.append(f"Qdrant unavailable: {type(exc).__name__}: {exc}")

    backend = ROOT / "backend"
    python = backend / "venv" / "Scripts" / "python.exe"
    try:
        current = subprocess.run(
            [str(python), "-m", "alembic", "current"],
            cwd=str(backend),
            capture_output=True,
            text=True,
            timeout=30,
        )
        heads = subprocess.run(
            [str(python), "-m", "alembic", "heads"],
            cwd=str(backend),
            capture_output=True,
            text=True,
            timeout=30,
        )
        current_text = (current.stdout + current.stderr).strip()
        heads_text = (heads.stdout + heads.stderr).strip()
        if current.returncode != 0 or heads.returncode != 0:
            failures.append("Alembic current/head command failed")
        else:
            head_ids = [line.split()[0] for line in heads_text.splitlines()
                        if line.strip() and not line.strip().startswith(("INFO", "WARN"))]
            if not head_ids:
                failures.append("Alembic head could not be determined")
            elif not any(head_id in current_text for head_id in head_ids):
                failures.append("Database is not at Alembic head")
    except Exception as exc:
        failures.append(f"Alembic unavailable: {type(exc).__name__}: {exc}")
    return failures


async def load_for_users(users, job_id, seconds, concurrency):
    endpoint_paths = ["/health", "/jobs/", "/candidates/", f"/jobs/{job_id}/results"]
    outcomes = []
    lock = asyncio.Lock()
    deadline = time.perf_counter() + seconds

    async def worker(index):
        token = users[index % len(users)]["token"]
        async with httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=httpx.Timeout(30),
            cookies={"access_token": token},
        ) as client:
            cursor = index % len(endpoint_paths)
            while time.perf_counter() < deadline:
                path = endpoint_paths[cursor % len(endpoint_paths)]
                cursor += 1
                start = time.perf_counter()
                try:
                    response = await client.get(path)
                    status = response.status_code
                    error = None
                except Exception as exc:
                    status = "exception"
                    error = str(exc)[:200]
                row = {"path": path, "status": status, "elapsed_ms": (time.perf_counter() - start) * 1000, "error": error}
                async with lock:
                    outcomes.append(row)

    started = time.perf_counter()
    await asyncio.gather(*(worker(i) for i in range(concurrency)))
    elapsed = time.perf_counter() - started
    status_counts = {}
    successful = []
    for row in outcomes:
        status_counts[str(row["status"])] = status_counts.get(str(row["status"]), 0) + 1
        if row["status"] == 200:
            successful.append(row["elapsed_ms"])
    return {
        "concurrency": concurrency,
        "duration_seconds": round(elapsed, 3),
        "requests": len(outcomes),
        "requests_per_minute": round(len(outcomes) / elapsed * 60, 2) if elapsed else 0,
        "status_counts": status_counts,
        "percentiles_meaningful": len(successful) >= 10,
        "percentiles_note": "HTTP 200 samples only" if len(successful) >= 10 else "Not meaningful: fewer than 10 HTTP 200 responses",
        "p50_ms_200_only": percentile(successful, 50),
        "p95_ms_200_only": percentile(successful, 95),
        "p99_ms_200_only": percentile(successful, 99),
        "successful_200": len(successful),
    }


async def main():
    failures = await preflight()
    if failures:
        print(json.dumps({"preflight": "FAIL", "failures": failures}, indent=2))
        return

    run_id, password, records = await seed()
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=httpx.Timeout(60)) as client_a, httpx.AsyncClient(base_url=BASE_URL, timeout=httpx.Timeout(60)) as client_b:
        token_a = await login(client_a, records["a"]["email"], password)
        token_b = await login(client_b, records["b"]["email"], password)
        users = [
            {"email": records["a"]["email"], "password": password, "token": token_a},
            {"email": records["b"]["email"], "password": password, "token": token_b},
        ]

        checks = {}
        missing = await httpx.AsyncClient(base_url=BASE_URL).__aenter__()
        try:
            response = await missing.get("/jobs/")
            checks["missing_token_jobs"] = response.status_code
            response = await missing.get("/jobs/", headers={"Cookie": "access_token=invalid-token"})
            checks["invalid_token_jobs"] = response.status_code
        finally:
            await missing.__aexit__(None, None, None)

        for name, client in (("tenant_a", client_a), ("tenant_b", client_b)):
            checks[name + "_own_jobs"] = (await client.get("/jobs/")).status_code
            checks[name + "_own_candidates"] = (await client.get("/candidates/")).status_code
            checks[name + "_own_results"] = (await client.get(f"/jobs/{records[name[-1]]['job_id']}/results")).status_code
        checks["tenant_b_read_tenant_a_job"] = (await client_b.get(f"/jobs/{records['a']['job_id']}")).status_code
        checks["tenant_b_read_tenant_a_results"] = (await client_b.get(f"/jobs/{records['a']['job_id']}/results")).status_code

    sweeps = {}
    for concurrency in (1, 5, 10):
        sweeps[str(concurrency)] = await load_for_users(users, records["a"]["job_id"], 30, concurrency)

    output = {
        "run_id": run_id,
        "seeded_records": records,
        "security_checks": checks,
        "load_sweeps": sweeps,
        "conditions": "Local uvicorn on port 5000, DB_SCHEMA=test_isolation, two synthetic users, no frontend.",
        "not_exercised": [
            "candidate cross-tenant object read/write (no candidate fixture seeded)",
            "webhook processing with a valid interview record",
            "valid/expired/tampered interview tokens",
            "worker retry and duplicate result idempotency",
        ],
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "api_v2.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({"security_checks": checks, "sweeps": sweeps}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
