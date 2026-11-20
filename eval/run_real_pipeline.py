"""Run the real ingestion, embedding, Qdrant retrieval, and LLM screening path.

Run this process with DB_SCHEMA=test_isolation. It uses only synthetic files
under eval/data and does not modify application source code.
"""
import asyncio
import hashlib
import json
import math
import statistics
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DATA = ROOT / "eval" / "data"
RESULTS = ROOT / "eval" / "results"
sys.path.insert(0, str(BACKEND))


def rankdata(values):
    ranked = [0.0] * len(values)
    for start in range(len(values)):
        end = start
        while end + 1 < len(values) and values[end + 1] == values[start]:
            end += 1
        rank = (start + 1 + end + 1) / 2
        for i in range(start, end + 1):
            ranked[i] = rank
    return ranked


def spearman(xs, ys):
    if len(xs) < 2:
        return None
    rx, ry = rankdata(xs), rankdata(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    numerator = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    denominator = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(numerator / denominator, 6) if denominator else 0.0


def ndcg(rows, k):
    values = [2 if row["label"] == "STRONG_FIT" else 1 if row["label"] == "PARTIAL_FIT" else 0 for row in rows[:k]]
    ideal = sorted(values, reverse=True)
    dcg = sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(values))
    idcg = sum((2**rel - 1) / math.log2(i + 2) for i, rel in enumerate(ideal))
    return round(dcg / idcg, 6) if idcg else 0.0


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, math.ceil(len(ordered) * p / 100) - 1)], 3)


def job_profile(job):
    if job == "backend":
        return {
            "role_summary": "Backend Engineer building production APIs and services",
            "required_skills": ["Python", "FastAPI", "PostgreSQL", "REST APIs"],
            "preferred_skills": ["Redis", "AWS", "Kubernetes", "testing"],
            "requirements": ["5+ years backend engineering experience"],
            "experience": {"minimum_years": 5},
            "education": {"preferred": "Bachelor degree"},
        }
    return {
        "role_summary": "Data Analyst producing reliable business insights",
        "required_skills": ["SQL", "Python", "pandas", "statistics"],
        "preferred_skills": ["Tableau", "ETL", "experimentation"],
        "requirements": ["3+ years analytics experience"],
        "experience": {"minimum_years": 3},
        "education": {"preferred": "Bachelor degree"},
    }


def label_for(path):
    stem = path.stem
    if "near_duplicate" in stem:
        return "STRONG_FIT"
    number = int(stem.split("_")[1])
    return "STRONG_FIT" if number <= 5 else "PARTIAL_FIT" if number <= 10 else "NOT_FIT"


def files_for(job):
    paths = []
    for path in sorted(DATA.iterdir()):
        if not path.is_file() or not path.name.startswith(job + "_"):
            continue
        if path.suffix == ".scanned_ocr" or "exact_copy" in path.stem:
            continue
        paths.append(path)
    return paths


async def main():
    from sqlalchemy import select
    from app.core.config import settings
    from app.db.session import AsyncSessionLocal
    from app.models.batch import ScreeningBatch
    from app.models.job import Job
    from app.models.organization import Organization
    from app.models.resume import Resume
    from app.models.screening import ScreeningResult
    from app.services import orchestrator as orchestrator_module
    from app.services.embeddings import embedding_router
    from app.services.llm_provider import GeminiProvider, GroqProvider, NvidiaProvider, OpenRouterProvider
    from app.services.model_registry import model_registry
    from app.services.screener import ScreenerService
    from app.services.vector_store import vector_store

    run_id = uuid.uuid4().hex[:12]
    metrics = {
        "run_id": run_id,
        "conditions": {
            "database_schema": settings.DB_SCHEMA or "public",
            "dataset": "existing eval/data synthetic files; exact copies excluded by DB hash uniqueness",
            "embedding_model": settings.EMBEDDING_MODEL,
            "llm_priority": settings.LLM_PROVIDER_PRIORITY,
            "qdrant_collection": settings.QDRANT_COLLECTION,
        },
        "files": [],
        "searches": {},
        "llm_attempts": [],
        "latencies_ms": {"parse": [], "embedding": [], "vector_search": [], "llm": [], "total": []},
    }

    async def timed_call(original, bucket, *args, **kwargs):
        start = time.perf_counter()
        result = await original(*args, **kwargs)
        metrics["latencies_ms"][bucket].append((time.perf_counter() - start) * 1000)
        return result

    original_embedding = embedding_router.generate_embedding
    async def wrapped_embedding(*args, **kwargs):
        return await timed_call(original_embedding, "embedding", *args, **kwargs)
    embedding_router.generate_embedding = wrapped_embedding

    original_search = vector_store.search
    async def wrapped_search(*args, **kwargs):
        start = time.perf_counter()
        result = await original_search(*args, **kwargs)
        metrics["latencies_ms"]["vector_search"].append((time.perf_counter() - start) * 1000)
        return result
    vector_store.search = wrapped_search

    original_get_extractor = orchestrator_module.get_extractor
    def wrapped_get_extractor(*args, **kwargs):
        extractor = original_get_extractor(*args, **kwargs)
        original_extract = extractor.extract
        async def wrapped_extract(*extract_args, **extract_kwargs):
            start = time.perf_counter()
            result = await original_extract(*extract_args, **extract_kwargs)
            metrics["latencies_ms"]["parse"].append((time.perf_counter() - start) * 1000)
            return result
        extractor.extract = wrapped_extract
        return extractor
    orchestrator_module.get_extractor = wrapped_get_extractor

    provider_classes = [GroqProvider, GeminiProvider, OpenRouterProvider, NvidiaProvider]
    for provider_class in provider_classes:
        original_provider_call = provider_class.generate_json
        provider_name = provider_class.provider_name
        async def wrapped_provider_call(self, model_name, prompt, schema, _original=original_provider_call, _name=provider_name):
            attempt = {"provider": _name, "model": model_name, "success": False}
            metrics["llm_attempts"].append(attempt)
            try:
                result = await _original(self, model_name, prompt, schema)
                attempt["success"] = bool(result)
                return result
            except Exception as exc:
                attempt["error"] = str(exc)[:200]
                raise
        provider_class.generate_json = wrapped_provider_call

    original_evaluate = ScreenerService.evaluate_candidate
    async def wrapped_evaluate(self, *args, **kwargs):
        start_attempts = len(metrics["llm_attempts"])
        start = time.perf_counter()
        result = await original_evaluate(self, *args, **kwargs)
        metrics["latencies_ms"]["llm"].append((time.perf_counter() - start) * 1000)
        attempts = metrics["llm_attempts"][start_attempts:]
        result["_eval_attempts"] = len(attempts)
        result["_eval_provider"] = attempts[-1]["provider"] if attempts else None
        return result
    ScreenerService.evaluate_candidate = wrapped_evaluate

    async with AsyncSessionLocal() as session:
        organization = Organization(name=f"Evaluation Tenant {run_id}")
        session.add(organization)
        await session.flush()
        jobs = {}
        batches = {}
        for job_name in ("backend", "analyst"):
            job = Job(
                organization_id=organization.id,
                title="Synthetic " + ("Backend Engineer" if job_name == "backend" else "Data Analyst"),
                description=json.dumps(job_profile(job_name)),
                job_profile=job_profile(job_name),
                embedding_profile=settings.EMBEDDING_MODEL,
                embedding_status="READY",
                status="ACTIVE",
            )
            session.add(job)
            await session.flush()
            batch = ScreeningBatch(job_id=job.id, batch_type="UPLOAD", total_resumes=len(files_for(job_name)))
            session.add(batch)
            await session.flush()
            jobs[job_name] = job
            batches[job_name] = batch
            for path in files_for(job_name):
                resume = Resume(
                    batch_id=batch.id,
                    job_id=job.id,
                    filename=path.name,
                    file_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
                    storage_key=str(path.resolve()),
                    status="UPLOADED",
                    workflow_stage="UPLOADED",
                )
                session.add(resume)
                await session.flush()
                metrics["files"].append({
                    "resume_id": resume.id,
                    "job": job_name,
                    "filename": path.name,
                    "label": label_for(path),
                    "status": "seeded",
                })
        await session.commit()

        from app.services.orchestrator import orchestrator
        for row in metrics["files"]:
            start = time.perf_counter()
            try:
                await asyncio.wait_for(orchestrator.process_candidate(row["resume_id"]), timeout=120)
                row["status"] = "processed"
            except Exception as exc:
                row["status"] = "failed"
                row["error"] = str(exc)[:300]
            row["total_ms"] = round((time.perf_counter() - start) * 1000, 3)
            metrics["latencies_ms"]["total"].append(row["total_ms"])

        screener = ScreenerService()
        for job_name, job in jobs.items():
            await session.refresh(job)
            search_key = job_name
            before = len(metrics["latencies_ms"]["vector_search"])
            try:
                results = await asyncio.wait_for(screener.screen_job(session, job, limit=50), timeout=300)
                await session.commit()
                metrics["screening_" + search_key] = {
                    "result_count": len(results),
                    "llm_result_count": sum(1 for r in results if r.score is not None),
                    "decisions": {},
                }
                for result in results:
                    metrics["screening_" + search_key]["decisions"][str(result.resume_id)] = result.decision
            except Exception as exc:
                metrics["screening_" + search_key] = {"error": str(exc)[:500]}
            if len(metrics["latencies_ms"]["vector_search"]) > before:
                metrics["searches"][search_key] = {"search_latency_recorded": True}

        rows = (await session.execute(
            select(ScreeningResult, Resume.filename, Resume.job_id, Job.title)
            .join(Resume, Resume.id == ScreeningResult.resume_id)
            .join(Job, Job.id == ScreeningResult.job_id)
            .where(Job.organization_id == organization.id)
        )).all()
        row_by_id = {r["resume_id"]: r for r in metrics["files"]}
        scored = []
        for result, filename, job_id, title in rows:
            file_row = row_by_id.get(result.resume_id, {})
            scored.append({
                "resume_id": result.resume_id,
                "job": file_row.get("job"),
                "filename": filename,
                "label": file_row.get("label"),
                "score": result.score,
                "decision": result.decision,
                "semantic_score": result.semantic_score,
                "notes": result.notes,
            })
        metrics["screening_results"] = scored

        # Re-evaluate the first 10 available resumes three times each.
        consistency = []
        for file_row in metrics["files"][:10]:
            resume = await session.get(Resume, file_row["resume_id"])
            job = await session.get(Job, resume.job_id)
            profile = (await session.execute(
                select(__import__("app.models.profile", fromlist=["CandidateProfile"]).CandidateProfile)
                .where(__import__("app.models.profile", fromlist=["CandidateProfile"]).CandidateProfile.resume_id == resume.id)
            )).scalar_one_or_none()
            if not profile:
                continue
            profile_dict = {
                "summary": profile.summary, "total_experience_years": profile.total_experience_years,
                "experience": profile.experience, "skills": profile.skills, "projects": profile.projects,
                "education": profile.education, "certifications": profile.certifications,
            }
            scores, decisions = [], []
            for _ in range(3):
                try:
                    value = await asyncio.wait_for(screener.evaluate_candidate(job.job_profile, profile_dict), timeout=60)
                    scores.append(float(value.get("score", 0)))
                    decisions.append(value.get("decision"))
                except Exception:
                    pass
            consistency.append({
                "resume_id": resume.id, "label": file_row["label"], "scores": scores,
                "score_stddev": round(statistics.pstdev(scores), 6) if len(scores) > 1 else None,
                "decision_agreement": len(set(decisions)) == 1 if decisions else None,
            })
        metrics["consistency"] = consistency
        metrics["organization_id"] = organization.id
        metrics["job_ids"] = {name: job.id for name, job in jobs.items()}
        metrics["batch_ids"] = {name: batch.id for name, batch in batches.items()}

    # Remove vectors for the two synthetic jobs; DB rows remain in isolated test schema.
    for job_id in metrics["job_ids"].values():
        try:
            await vector_store.delete_points_by_filter(settings.QDRANT_COLLECTION, {"job_id": job_id})
        except Exception as exc:
            metrics.setdefault("cleanup_errors", []).append(str(exc)[:200])

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "pipeline_v2.json").write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")
    print(json.dumps({
        "files": len(metrics["files"]),
        "processed": sum(row["status"] == "processed" for row in metrics["files"]),
        "failed": sum(row["status"] == "failed" for row in metrics["files"]),
        "screening_results": len(metrics.get("screening_results", [])),
        "llm_attempts": len(metrics["llm_attempts"]),
        "consistency_rows": len(metrics.get("consistency", [])),
        "job_ids": metrics["job_ids"],
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
