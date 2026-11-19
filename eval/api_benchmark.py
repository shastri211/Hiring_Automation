"""Small local HTTP benchmark for the backend API.

The benchmark does not change application code or seed a database. It records
all status codes and calculates latency percentiles only for HTTP 200 results.
"""
import asyncio
import json
import math
import statistics
import time
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:5000"
ENDPOINTS = {
    "health": "/health",
    "job_list": "/jobs/",
    "candidate_list": "/candidates/",
    "screening_results": "/jobs/1/results",
}
RESULTS = Path(__file__).resolve().parent / "results"


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil((p / 100) * len(ordered)) - 1)
    return round(ordered[index], 3)


async def one_request(client, endpoint):
    start = time.perf_counter()
    try:
        response = await client.get(endpoint)
        error = None
        status = response.status_code
    except Exception as exc:
        status = "exception"
        error = str(exc)[:200]
    return {
        "status": status,
        "elapsed_ms": (time.perf_counter() - start) * 1000,
        "error": error,
    }


async def run_batch(total, concurrency):
    jobs = [list(ENDPOINTS.values())[i % len(ENDPOINTS)] for i in range(total)]
    semaphore = asyncio.Semaphore(concurrency)

    async def limited(client, endpoint):
        async with semaphore:
            return await one_request(client, endpoint)

    start = time.perf_counter()
    timeout = httpx.Timeout(connect=3, read=5, write=3, pool=5)
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=timeout) as client:
        results = await asyncio.gather(*(limited(client, endpoint) for endpoint in jobs))
    duration = time.perf_counter() - start

    by_endpoint = {}
    for name, endpoint in ENDPOINTS.items():
        rows = [row for row, requested in zip(results, jobs) if requested == endpoint]
        status_counts = {}
        for row in rows:
            key = str(row["status"])
            status_counts[key] = status_counts.get(key, 0) + 1
        successful = [row["elapsed_ms"] for row in rows if row["status"] == 200]
        by_endpoint[name] = {
            "path": endpoint,
            "requests": len(rows),
            "status_counts": status_counts,
            "p50_ms_200_only": percentile(successful, 50),
            "p95_ms_200_only": percentile(successful, 95),
            "p99_ms_200_only": percentile(successful, 99),
            "successful_200_count": len(successful),
            "mean_ms_all_statuses": round(statistics.mean(row["elapsed_ms"] for row in rows), 3),
        }

    all_200 = [row["elapsed_ms"] for row in results if row["status"] == 200]
    total_status = {}
    for row in results:
        key = str(row["status"])
        total_status[key] = total_status.get(key, 0) + 1
    achieved_rpm = len(results) / duration * 60 if duration else 0
    return {
        "requests": total,
        "concurrency": concurrency,
        "duration_seconds": round(duration, 3),
        "achieved_requests_per_minute": round(achieved_rpm, 2),
        "target_5000_rpm_met": achieved_rpm >= 5000,
        "under_200ms_p95_for_200s": bool(all_200) and percentile(all_200, 95) < 200,
        "status_counts": total_status,
        "p50_ms_200_only": percentile(all_200, 50),
        "p95_ms_200_only": percentile(all_200, 95),
        "p99_ms_200_only": percentile(all_200, 99),
        "endpoints": by_endpoint,
    }


async def main():
    # Short concurrency sweeps plus one 5,000-request capacity run.
    sweeps = {str(c): await run_batch(400, c) for c in (1, 5, 10)}
    capacity = await run_batch(5000, 20)
    output = {
        "base_url": BASE_URL,
        "conditions": {
            "auth": "No auth token supplied; protected routes intentionally measure rejection behavior.",
            "database": "No data seeded; routes may return environment-dependent 401/5xx statuses.",
            "percentiles": "Computed only from HTTP 200 responses, as requested.",
        },
        "sweeps": sweeps,
        "capacity_5000_requests": capacity,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "api_benchmark.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps({
        "capacity": {
            "rpm": capacity["achieved_requests_per_minute"],
            "target_met": capacity["target_5000_rpm_met"],
            "p95_200_ms": capacity["p95_ms_200_only"],
            "statuses": capacity["status_counts"],
        },
        "sweeps": {
            key: {
                "rpm": value["achieved_requests_per_minute"],
                "statuses": value["status_counts"],
                "p95_200_ms": value["p95_ms_200_only"],
            }
            for key, value in sweeps.items()
        },
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
