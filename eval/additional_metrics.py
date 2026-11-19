"""Measure backend component metrics that do not require external LLM/Qdrant."""
import asyncio
import hashlib
import json
import statistics
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DATA = ROOT / "eval" / "data"
RESULTS = ROOT / "eval" / "results"
sys.path.insert(0, str(BACKEND))


def percentile(values, p):
    values = sorted(values)
    if not values:
        return None
    index = min(len(values) - 1, max(0, int((p / 100) * len(values) + 0.999) - 1))
    return round(values[index], 3)


def measure_hashing():
    files = [p for p in DATA.iterdir() if p.is_file()]
    timings = []
    total_bytes = 0
    for path in files:
        start = time.perf_counter()
        hashlib.sha256(path.read_bytes()).hexdigest()
        timings.append((time.perf_counter() - start) * 1000)
        total_bytes += path.stat().st_size
    elapsed = sum(timings) / 1000
    return {
        "files": len(files),
        "bytes": total_bytes,
        "total_hash_time_ms": round(sum(timings), 3),
        "p50_ms": percentile(timings, 50),
        "p95_ms": percentile(timings, 95),
        "files_per_second": round(len(files) / elapsed, 2) if elapsed else None,
        "mb_per_second": round(total_bytes / elapsed / 1_000_000, 3) if elapsed else None,
    }


def measure_import():
    times = []
    command = [str(BACKEND / "venv" / "Scripts" / "python.exe"), "-c", "import app.main"]
    for _ in range(3):
        start = time.perf_counter()
        completed = subprocess.run(command, cwd=BACKEND, capture_output=True, text=True, timeout=30)
        times.append((time.perf_counter() - start) * 1000)
        if completed.returncode != 0:
            return {"status": "N/A", "reason": completed.stderr[-300:]}
    return {
        "runs": 3,
        "p50_ms": percentile(times, 50),
        "p95_ms": percentile(times, 95),
        "status": "success",
    }


def measure_parsing():
    data = json.loads((RESULTS / "per_resume.json").read_text(encoding="utf-8"))
    successful = [row for row in data if row["success"]]
    elapsed = sum(row["elapsed_ms"] for row in successful) / 1000
    return {
        "successful_files": len(successful),
        "total_files": len(data),
        "successful_files_per_second": round(len(successful) / elapsed, 2) if elapsed else None,
        "successful_files_per_minute": round(len(successful) / elapsed * 60, 2) if elapsed else None,
        "total_successful_parse_time_ms": round(sum(row["elapsed_ms"] for row in successful), 3),
    }


def measure_auth():
    from app.services.auth import create_access_token, decode_access_token, hash_password, verify_password
    password = "SyntheticMetricPassword!123"
    hash_start = time.perf_counter()
    password_hash = hash_password(password)
    hash_ms = (time.perf_counter() - hash_start) * 1000
    verify_times = []
    decode_times = []
    token = create_access_token(123, password_hash)
    for _ in range(100):
        start = time.perf_counter()
        verify_password(password, password_hash)
        verify_times.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        decoded = decode_access_token(token)
        decode_times.append((time.perf_counter() - start) * 1000)
        if decoded is None:
            raise RuntimeError("Generated token did not decode")
    return {
        "bcrypt_hash_one_ms": round(hash_ms, 3),
        "bcrypt_verify_100_p50_ms": percentile(verify_times, 50),
        "bcrypt_verify_100_p95_ms": percentile(verify_times, 95),
        "jwt_decode_100_p50_ms": percentile(decode_times, 50),
        "jwt_decode_100_p95_ms": percentile(decode_times, 95),
        "valid_token_round_trips": 100,
    }


async def measure_redis():
    import redis.asyncio as redis
    client = redis.Redis(host="127.0.0.1", port=6379, db=15, decode_responses=True)
    stream = "eval_metrics_" + uuid.uuid4().hex
    group = "eval_group_" + uuid.uuid4().hex
    try:
        ping_times = []
        for _ in range(100):
            start = time.perf_counter()
            await client.ping()
            ping_times.append((time.perf_counter() - start) * 1000)
        await client.xgroup_create(stream, group, id="0", mkstream=True)
        round_trips = []
        for i in range(50):
            start = time.perf_counter()
            message_id = await client.xadd(stream, {"action": "eval", "n": str(i)})
            messages = await client.xreadgroup(group, "eval-consumer", {stream: ">"}, count=1, block=1000)
            if not messages or not messages[0][1]:
                raise RuntimeError("Redis stream read returned no message")
            await client.xack(stream, group, message_id)
            round_trips.append((time.perf_counter() - start) * 1000)
        return {
            "ping_100_p50_ms": percentile(ping_times, 50),
            "ping_100_p95_ms": percentile(ping_times, 95),
            "stream_enqueue_read_ack_50_p50_ms": percentile(round_trips, 50),
            "stream_enqueue_read_ack_50_p95_ms": percentile(round_trips, 95),
            "stream_round_trips": 50,
        }
    finally:
        await client.delete(stream)
        await client.close()


async def main():
    output = {
        "parsing_throughput": measure_parsing(),
        "sha256_dedupe_throughput": measure_hashing(),
        "app_import_time": measure_import(),
        "auth_crypto": measure_auth(),
        "redis": await measure_redis(),
        "conditions": "Local synthetic files, Redis localhost, bcrypt/JWT in existing venv; no LLM/Qdrant/DB substitution.",
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "additional_metrics.json").write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
