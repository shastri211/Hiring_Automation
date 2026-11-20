# Backend Evaluation Report (v3)

## Environment

| Check | Result |
|---|---|
| Backend runtime | Running at `http://127.0.0.1:8001`; `/health` returned HTTP 200 with `db`, `redis`, and `qdrant` all `ok` |
| Database | Alembic current revision `d9a6e3f1c4b5`, which is the head |
| Redis | `PING=True` |
| Qdrant | Qdrant Cloud HTTP 200 from configured `QDRANT_URL`, collection `resume_candidates_768` |
| Backend virtual environment | `backend\venv` |
| Docker | Not used |
| Application code | Not modified |
| Synthetic data | Two synthetic tenants/users/jobs; synthetic candidates, resumes, and interviews |

The initial preflight incorrectly checked local Qdrant `127.0.0.1:6333` and backend port 5000. The project is configured for Qdrant Cloud and uvicorn is documented/run on port 8001. The script was corrected and rerun. Preflight now checks the configured Qdrant URL plus API key.

## Part 1: API Load

| Concurrency / endpoint | Successful HTTP 200 | p50 | p95 | p99 | Throughput | Error counts |
|---:|---:|---:|---:|---:|---:|---|
| 1 user, 30 s, `/health`, `/jobs/`, `/candidates/`, `/jobs/{id}/results` | 461 | 11.065 ms | 280.257 ms | 372.309 ms | 919.86 req/min | 200: 461 |
| 5 users, 30 s, `/health`, `/jobs/`, `/candidates/`, `/jobs/{id}/results` | 2084 | 16.304 ms | 201.621 ms | 425.125 ms | 4633.69 req/min | 200: 2084; 404: 234 |
| 10 users, 30 s, `/health`, `/jobs/`, `/candidates/`, `/jobs/{id}/results` | 1748 | 86.432 ms | 304.463 ms | 554.988 ms | 3988.15 req/min | 200: 1748; 404: 249 |

Percentiles are 200-only and would be marked not meaningful for fewer than 10 successful requests. No percentile or throughput number is reported because no API run occurred.

## Part 2: Security and Isolation

| Check | Blocked / total or status | Result |
|---|---:|---|
| Tenant B reads Tenant A job | 1/1 blocked | 404 |
| Tenant B modifies Tenant A job | 1/1 blocked | 404 |
| Tenant B reads Tenant A candidate | 1/1 blocked | 404 |
| Tenant B modifies Tenant A candidate | 1/1 blocked | 404 |
| Tenant B reads/modifies guessed Tenant A result ID | 1/1 blocked | 404 |
| Missing auth token | Rejected | 401 |
| Invalid auth token | Rejected | 401 |
| Expired auth token | Rejected | 401 |
| Tampered auth token | Rejected | 401 |
| Dograh status payload processing | Processed | 200; interview status `COMPLETED` |
| Dograh transcript payload processing | Processed | 200; transcript persisted |
| Dograh evaluation payload processing | Processed | 200; evaluation persisted |
| Webhook with no auth/signature | Accepted | 200 - finding, not a strength |
| Valid interview link | Works | 200 |
| Expired interview link | Rejected | 410 |
| Tampered interview link | Rejected | 404 |

The source configuration and runtime both showed Dograh webhook authentication accepting unauthenticated requests. The payloads were applied to the synthetic valid interview fixture.

## Part 3: Worker Reliability

| Check | Result |
|---|---|
| LLM call fails once, retry with backoff, then succeeds | Eval mock: 1 failure, retry attempt 1, configured backoff 59.987 s, success after retry metadata cleared |
| Same resume enqueued twice; only one result created | Pass: 2 simulated enqueue operations; database result count 1 |
| 3 concurrent resumes | N/A - worker test not run |
| 3 concurrent resumes throughput | N/A resumes/minute |
| Sequential 3-resume throughput | 3.866311 resumes/minute, measured in the v2 synthetic end-to-end pipeline run |

## Failed or weak cases

- The first report run used the wrong endpoints: local port `6333` for Qdrant Cloud and backend port `5000` instead of `8001`.
- The corrected preflight passes backend `/health`, Redis PING, Qdrant Cloud, and Alembic head.
- Redis PING passed.
- Alembic current was `d9a6e3f1c4b5`, and this was confirmed as the head.
- No API, tenant-isolation, auth, webhook, interview-token, retry, idempotency, or concurrency result was generated.
- No capacity, percentile, status-code, or worker-throughput claim is inferred.
- The v2 `httpx.ReadTimeout` was addressed in [`run_api_v2.py`](../run_api_v2.py): preflight now gates the run, login is sequential once per user, 60-second login timeout is used, 30-second request timeout is used, and timed-out requests are not retried.

## Resume-ready numbers

Only previously measured values are included here, with their conditions:

- **468 passed, 0 failed** backend tests, on a full-suite run in the local Windows `backend\venv`.
- **76%** full-suite line coverage under the v2 run.
- **1.000000** nDCG@5 and nDCG@10 for each synthetic backend-engineer and data-analyst profile.
- **1.000000** retrieval Hit@5 and retrieval Recall@10.
- **0.879883** Spearman correlation on 22 LLM-scored synthetic rows.
- **1.000000** adaptive-gate STRONG_FIT recall (12/12).
- **0.000000** false-shortlist rate and **0.000000** false-reject rate on the 30-row synthetic set.
- **3.866311 resumes/minute** sequential end-to-end throughput.
- **17,095.448 ms p50** and **19,276.228 ms p95** total pipeline latency per synthetic resume.
- **919.86 req/min** with 1 concurrent user, 30 seconds, 461 HTTP 200 responses.
- **4633.69 req/min** with 5 concurrent users, 30 seconds, 2084 HTTP 200 responses.
- **3988.15 req/min** with 10 concurrent users, 30 seconds, 1748 HTTP 200 responses.
- **11.065 ms p50, 280.257 ms p95, 372.309 ms p99** from 461 HTTP 200 responses at concurrency 1.
- **16.304 ms p50, 201.621 ms p95, 425.125 ms p99** from 2084 HTTP 200 responses at concurrency 5.
- **86.432 ms p50, 304.463 ms p95, 554.988 ms p99** from 1748 HTTP 200 responses at concurrency 10.
