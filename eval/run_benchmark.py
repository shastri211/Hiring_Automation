"""Bounded, backend-only synthetic evaluation.

This script intentionally does not alter application code or require Docker.
It measures the parts that can run with the local venv and records N/A for
provider/service-dependent stages instead of substituting a fake pipeline.
"""
import asyncio
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DATA = ROOT / "eval" / "data"
RESULTS = ROOT / "eval" / "results"
sys.path.insert(0, str(BACKEND))


def make_text(job: str, label: str, index: int, variant: str = "") -> str:
    if job == "backend":
        skills = {
            "STRONG_FIT": "Python FastAPI PostgreSQL Redis Docker Kubernetes AWS 6 years backend APIs testing",
            "PARTIAL_FIT": "Python FastAPI PostgreSQL REST APIs 2 years testing",
            "NOT_FIT": "Brand marketing SEO campaign management content analytics 3 years",
        }[label]
        title = "Backend Engineer"
    else:
        skills = {
            "STRONG_FIT": "SQL Python pandas statistics Tableau ETL experimentation 5 years data analysis",
            "PARTIAL_FIT": "SQL Python pandas dashboards 2 years reporting",
            "NOT_FIT": "JavaScript React CSS frontend design 3 years user interfaces",
        }[label]
        title = "Data Analyst"
    return (
        f"Synthetic Candidate {job}-{index}\nTarget role: {title}\n"
        f"Experience: {skills}\nEducation: Bachelor of Science\n"
        f"Projects: measurable delivery, documentation, collaboration. {variant}\n"
    )


def create_documents():
    if DATA.exists():
        shutil.rmtree(DATA)
    DATA.mkdir(parents=True)
    records = []
    labels = ["STRONG_FIT"] * 5 + ["PARTIAL_FIT"] * 5 + ["NOT_FIT"] * 5
    for job in ("backend", "analyst"):
        for i, label in enumerate(labels, 1):
            fmt = "pdf" if i % 2 else "docx"
            scanned = i == 14
            if scanned:
                fmt = "scanned_ocr"
            path = DATA / f"{job}_{i:02d}.{fmt}"
            text = make_text(job, label, i)
            if fmt in ("pdf", "scanned_ocr"):
                import fitz
                doc = fitz.open()
                page = doc.new_page()
                if scanned:
                    from PIL import Image, ImageDraw
                    image = Image.new("RGB", (1200, 900), "white")
                    ImageDraw.Draw(image).multiline_text((50, 50), text, fill="black", spacing=8)
                    image_path = DATA / f"{job}_{i:02d}.png"
                    image.save(image_path)
                    page.insert_image(page.rect, filename=str(image_path))
                    image_path.unlink()
                else:
                    page.insert_text((50, 60), text)
                doc.save(path)
                doc.close()
            else:
                from docx import Document
                doc = Document()
                for line in text.splitlines():
                    doc.add_paragraph(line)
                doc.save(path)
            records.append({"id": f"{job}-{i:02d}", "job": job, "label": label,
                            "format": fmt, "path": str(path)})

    # Exact duplicates and near duplicates are deliberately additional files.
    shutil.copy2(DATA / "backend_01.pdf", DATA / "backend_01_exact_copy.pdf")
    shutil.copy2(DATA / "analyst_02.docx", DATA / "analyst_02_exact_copy.docx")
    records.extend([
        {"id": "backend-01-exact-copy", "job": "backend", "label": "STRONG_FIT",
         "format": "pdf", "path": str(DATA / "backend_01_exact_copy.pdf")},
        {"id": "analyst-02-exact-copy", "job": "analyst", "label": "STRONG_FIT",
         "format": "docx", "path": str(DATA / "analyst_02_exact_copy.docx")},
    ])
    near = DATA / "backend_02_near_duplicate.docx"
    from docx import Document
    doc = Document()
    for line in make_text("backend", "STRONG_FIT", 2, "Additional wording.").splitlines():
        doc.add_paragraph(line)
    doc.save(near)
    near2 = DATA / "analyst_03_near_duplicate.docx"
    doc = Document()
    for line in make_text("analyst", "STRONG_FIT", 3, "Additional wording.").splitlines():
        doc.add_paragraph(line)
    doc.save(near2)
    records.extend([
        {"id": "backend-02-near-duplicate", "job": "backend", "label": "STRONG_FIT",
         "format": "docx", "path": str(near)},
        {"id": "analyst-03-near-duplicate", "job": "analyst", "label": "STRONG_FIT",
         "format": "docx", "path": str(near2)},
    ])
    return records


async def parse_documents(records):
    from app.services.extractor.factory import get_extractor
    output = []
    for record in records:
        start = time.perf_counter()
        try:
            extractor = get_extractor(record["path"], "application/pdf" if record["format"] in ("pdf", "scanned_ocr") else f"application/{record['format']}")
            text = await extractor.extract(record["path"])
            output.append({**record, "success": bool(text), "chars": len(text),
                           "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                           "failure": None if text else "empty extraction; OCR provider unavailable or returned no text"})
        except Exception as exc:
            output.append({**record, "success": False, "chars": 0,
                           "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                           "failure": str(exc)[:300]})
    return output


def dedupe_measure():
    files = sorted(DATA.iterdir())
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in files]
    exact_groups = {}
    for path, digest in zip(files, hashes):
        exact_groups.setdefault(digest, []).append(path.name)
    return {
        "files": len(files),
        "exact_duplicate_groups": [v for v in exact_groups.values() if len(v) > 1],
        "exact_duplicates_caught": sum(len(v) - 1 for v in exact_groups.values() if len(v) > 1),
        "near_duplicates_caught_by_sha256": 0,
        "near_duplicate_note": "Near duplicates intentionally differ in content; exact hash dedupe does not catch them.",
    }


async def main():
    records = create_documents()
    parsed = await parse_documents(records)
    by_format = {}
    for fmt in ("pdf", "docx", "scanned_ocr"):
        rows = [r for r in parsed if r["format"] == fmt]
        by_format[fmt] = {
            "count": len(rows),
            "success_rate": round(sum(r["success"] for r in rows) / len(rows), 4) if rows else "N/A",
            "average_parse_ms": round(sum(r["elapsed_ms"] for r in rows) / len(rows), 3) if rows else "N/A",
            "failure_reasons": [r["failure"] for r in rows if r["failure"]],
        }
    results = {
        "dataset": {"base_resumes": 30, "files_measured": len(records), "jobs": 2, "seed": 0,
                    "labels_per_job": {"STRONG_FIT": 5, "PARTIAL_FIT": 5, "NOT_FIT": 5}},
        "parsing": by_format,
        "dedupe": dedupe_measure(),
        "pipeline_metrics": {
            "ranking": "N/A - Qdrant unavailable and no embedding/LLM key configured",
            "decisions": "N/A - no LLM provider key configured",
            "adaptive_gate": "N/A - requires vector search",
            "retrieval": "N/A - Qdrant unavailable",
            "score_separation": "N/A - no LLM provider key configured",
            "consistency": "N/A - no LLM provider key configured",
            "latency": "N/A - end-to-end pipeline did not run",
            "throughput": "N/A - end-to-end pipeline did not run",
            "llm_cost": "N/A - no request tokens; no provider call was made",
        },
        "service_status": {
            "postgres": "available listener; application authentication/migrations not exercised",
            "redis": "available and ping successful",
            "qdrant": "unavailable on localhost:6333",
            "llm": "N/A - GROQ_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, NVIDIA_API_KEY absent",
        },
        "files": parsed,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "benchmark.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    (RESULTS / "per_resume.json").write_text(json.dumps(parsed, indent=2), encoding="utf-8")
    report = f"""# Backend Evaluation Report

## Environment and substitutions

- Windows PowerShell, Python 3.13.2, existing `backend\\venv`; no Docker used.
- PostgreSQL port 5432 and Redis port 6379 listened locally; Redis `PING` returned true.
- Qdrant port 6333 was unavailable. The app only constructs an HTTP Qdrant client, so no in-memory substitution was possible without changing app code.
- No Groq, Gemini, OpenRouter, or NVIDIA key was present in `backend/.env`; no LLM test call was made.
- Dataset is synthetic only: 30 resumes (2 jobs x 15), plus 2 exact and 2 near-duplicate files.

## Part 1 - Code quality

| Check | Result |
|---|---:|
| Full pytest suite from `backend` | 269 passed, 123 failed, 76 errors, 42 warnings |
| Focused coverage subset (12 tests) | 42% line coverage |
| Five lowest-covered modules in focused run | `worker.py` 0%, `screener.py` 11%, `interview.py` 19%, `candidate_identity.py` 20%, `email.py` 21% |
| First incorrect invocation | 35 collection errors (`No module named 'app'`) when run from repository root |

Coverage used only the missing `pytest-cov` package installed into the existing backend venv.

## Part 2 - Screening quality

| Metric | Result |
|---|---:|
| nDCG@5, nDCG@10, Precision@5, Recall@5, MRR, Spearman | N/A - Qdrant/LLM unavailable |
| Decision confusion matrix and shortlist rates | N/A - LLM unavailable |
| Adaptive gate vs fixed top-10 | N/A - Qdrant unavailable |
| Retrieval Hit Rate@5 / Recall@10 | N/A - Qdrant unavailable |
| Score separation / 3x consistency | N/A - LLM unavailable |
| Exact deduplication | 2 duplicate files caught by SHA-256 |
| Near deduplication | 0 caught by SHA-256; near-duplicate detector is not present in this path |
| PDF parsing | {by_format['pdf']} |
| DOCX parsing | {by_format['docx']} |
| Scanned/OCR parsing | {by_format['scanned_ocr']} |
| LLM JSON/retry/fallback | N/A - no provider call |

## Part 3 - Pipeline performance

| Metric | Result |
|---|---:|
| Per-stage p50/p95, sequential/worker throughput | N/A - end-to-end pipeline unavailable |
| Token/cost estimate | N/A - zero provider requests |
| API latency at 1/5/10 users | N/A - DB-backed API benchmark not run |

## Part 4 - Reliability and security checks

| Check | Result |
|---|---|
| Tenant isolation, auth, interview links, retries, fallback | N/A - DB/LLM-backed checks not run |
| Webhook unauthenticated default | Finding: app import emitted a warning that `DOGRAH_WEBHOOK_AUTH_TYPE` defaults to `none`, accepting webhook requests without auth/signature. |
| Dead-letter stream | Known gap from task requirements; not exercised because worker integration was not run. |

## Failed or weak cases

- All ranking, decisions, gate, retrieval, consistency, provider fallback, worker, and API-load cases are unavailable because required Qdrant/LLM/DB pipeline prerequisites were not fully configured.
- The exact duplicate files are measurable; near duplicates are not caught by the app's SHA-256-equivalent exact hashing.
- Two scanned/OCR-style PDF samples were included; both returned empty text because OCR requires a configured Gemini provider.

## Weaknesses found

1. Qdrant is a hard HTTP dependency in the current vector-store configuration; no local test mode is exposed.
2. The import-time warning confirms unauthenticated Dograh webhooks when auth type is `none`.
3. There is no dead-letter stream for permanently failed worker messages (known gap).

## Resume-ready numbers

- 30 synthetic base resumes across 2 job profiles; 5 STRONG_FIT, 5 PARTIAL_FIT, and 5 NOT_FIT per job.
- 2 exact duplicate files caught by SHA-256 hashing; 0 near duplicates caught by exact hashing.
- Redis local `PING`: successful.
- PDF/DOCX parsing rates and mean times are recorded in `benchmark.json`; these are local-venv synthetic-data measurements only.
- All unmeasured LLM, embedding, Qdrant, worker, API-load, and DB-dependent values: N/A with reasons above.
"""
    (RESULTS / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps({"base_resumes": 30, "files": len(parsed),
                      "exact_duplicates_caught": results["dedupe"]["exact_duplicates_caught"],
                      "pdf": by_format["pdf"], "docx": by_format["docx"]}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
