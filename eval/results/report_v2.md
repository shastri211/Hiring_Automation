# Backend Evaluation Report (v2)

## Conditions and substitutions

| Item | Measured condition |
|---|---|
| Host/runtime | Windows PowerShell, Python 3.13.2, `backend\venv` |
| Data | 30 synthetic files, 2 job profiles; no real candidate data |
| Database | Local PostgreSQL, schema `test_isolation`, Alembic `d9a6e3f1c4b5` |
| Redis | Local Redis, `PING=True` |
| Vector store | Qdrant available at the configured localhost endpoint; collection `resume_candidates_768` |
| Embeddings | Gemini `gemini-embedding-2`, 768 dimensions |
| LLM | Groq-first routing; all recorded attempts used Groq |
| Docker | Not used |
| Application code | Not modified |

The pipeline JSON and per-resume details are in [`pipeline_v2.json`](./pipeline_v2.json) and [`metrics_v2.json`](./metrics_v2.json). The authenticated API run did not complete: it timed out during login, so API-load and dependent authenticated security results below are **N/A**, not inferred.

## Preflight

| Check | Result |
|---|---|
| App import | Pass |
| App schema | `d9a6e3f1c4b5 (head)` |
| Test schema | `d9a6e3f1c4b5 (head)` |
| Qdrant health | HTTP 200 |
| Redis PING | `True` |
| Tiny LLM JSON call | `{"ok": true}` |
| Keys present | Groq and Gemini; OpenRouter and NVIDIA absent |

## Part 1: Code quality

| Measure | Result |
|---|---:|
| Full pytest | 468 passed, 0 failed, 0 errors, 50 warnings |
| Full-suite line coverage | 76% |
| Lowest-covered modules | `app/worker.py` 0%; `app/services/screener.py` 11%; `app/services/interview.py` 19%; `app/services/candidate_identity.py` 20%; `app/services/email.py` 21% |
| CI workflow | Backend dependency install, PostgreSQL/Redis services, Alembic migrations/check, pytest; frontend lint/build was not run |

## Part 2: Screening quality

### Dataset and dedupe

| Ground truth | Count in 30 processed rows |
|---|---:|
| STRONG_FIT | 12 |
| PARTIAL_FIT | 10 |
| NOT_FIT | 8 |

The processed set contains near-duplicate variants. Exact duplicate files were excluded by the database `(job_id, file_hash)` uniqueness constraint. In the original 34-file source set, 2 exact duplicate files were caught and 0 near duplicates were caught by SHA-256.

### Ranking and retrieval

| Metric | Backend Engineer | Data Analyst |
|---|---:|---:|
| nDCG@5 | 1.000000 | 1.000000 |
| nDCG@10 | 1.000000 | 1.000000 |
| Precision@5 (STRONG_FIT) | 1.000000 | 1.000000 |
| Recall@5 (STRONG_FIT) | 0.833333 | 0.833333 |
| MRR first STRONG_FIT | 1.000000 | 1.000000 |
| Retrieval Hit@5 | 1.000000 | 1.000000 |
| Retrieval Recall@10 | 1.000000 | 1.000000 |

The final-ranking metrics use the recorded LLM score, with pre-screened rows ranked after scored rows. Retrieval metrics use embedding semantic similarity before LLM evaluation.

| Measure | Result |
|---|---:|
| Spearman score vs ground-truth order | 0.879883 |
| Spearman population | 22 scored rows; NOT_FIT rows were pre-screened and had no LLM score |

### Decisions and gate

| Ground truth \ Decision | SHORTLIST | REVIEW | REJECT |
|---|---:|---:|---:|
| STRONG_FIT | 11 | 1 | 0 |
| PARTIAL_FIT | 0 | 4 | 6 |
| NOT_FIT | 0 | 0 | 8 |

| Measure | Result |
|---|---:|
| False-shortlist rate (NOT_FIT → SHORTLIST) | 0/8 = 0.000000 |
| False-reject rate (STRONG_FIT → REJECT) | 0/12 = 0.000000 |
| Adaptive gate STRONG_FIT recall | 1.000000 (12/12) |
| Fixed top-N=10 STRONG_FIT recall | 1.000000 (12/12) |
| Average candidates sent to LLM | 11.0 per job |

### Score separation and consistency

| Class | Scored rows | Mean score | p50 |
|---|---:|---:|---:|
| STRONG_FIT | 12 | 90.416667 | 90.0 |
| PARTIAL_FIT | 10 | 46.000000 | 45.0 |
| NOT_FIT | 0 | N/A | N/A |

NOT_FIT scores are N/A because all 8 were rejected by the adaptive pre-screen gate before LLM scoring.

| Consistency measure | Result |
|---|---:|
| Resumes re-evaluated | 10 |
| Runs per resume | 3 |
| Mean score standard deviation | 3.190593 |
| Decision agreement rate | 1.000000 |

### Parsing and LLM reliability

| Format | Result |
|---|---|
| Text PDF | 17/17 = 100%; average 24.211 ms |
| DOCX | 15/15 = 100%; average 33.130 ms |
| Scanned/OCR-style PDF | 0/2 = 0%; empty extraction because OCR provider was unavailable in the parsing run |
| Live pipeline rows | 30/30 processed successfully |
| LLM attempts | 82 |
| Valid JSON on first try | 82/82 = 1.000000 |
| Retry rate | N/A; retry events were not persisted separately |
| Providers used | Groq only |
| Fallback-provider usage | 0 recorded |

## Part 3: Pipeline performance

| Stage | Samples | p50 (ms) | p95 (ms) |
|---|---:|---:|---:|
| Parsing | 30 | 6.070 | 42.138 |
| Embedding | 32 | 765.077 | 1505.825 |
| Vector search | 2 | 197.110 | 1041.808 |
| LLM evaluation | 52 | 15249.595 | 18946.656 |
| Total per resume | 30 | 17095.448 | 19276.228 |

| Throughput/cost measure | Result |
|---|---:|
| Sequential processed throughput | 3.866311 resumes/minute |
| Worker concurrency 3 | N/A; authenticated worker benchmark was not run |
| Token/cost estimate | N/A; token counts were not persisted and no verified pricing calculation was completed |

### API load

| Concurrency | Result |
|---:|---|
| 1 user, 30 seconds | N/A: benchmark timed out during login |
| 5 users, 30 seconds | N/A: benchmark did not reach this sweep |
| 10 users, 30 seconds | N/A: benchmark did not reach this sweep |
| 5,000 requests/minute under 200 ms | **Not demonstrated**; no valid authenticated 200-only percentile sample |

## Part 4: Reliability and security

| Check | Result |
|---|---|
| Tenant A/B read isolation | N/A; benchmark timed out before checks completed |
| Tenant A/B modification isolation | N/A; benchmark timed out before checks completed |
| Missing/invalid token rejection | N/A for this run; no completed authenticated benchmark artifact |
| Webhook payload processing | N/A; no completed interview fixture check |
| Unauthenticated webhook finding | Configuration default is `none`; this remains a security weakness requiring deployment hardening |
| Interview token valid/expired/tampered | N/A |
| Worker retry/backoff | N/A |
| Duplicate processing creates one result | N/A |
| Forced provider fallback | N/A; no forced-failure result was persisted |
| Dead-letter stream | Known gap; no dead-letter stream is implemented |

## Failed or weak cases

- The API benchmark failed with `httpx.ReadTimeout` during concurrent login, before producing `api_v2.json`.
- Therefore API p50/p95/p99, 5,000-request capacity, tenant isolation, auth behavior, interview-token behavior, worker retry, and forced-fallback metrics are N/A.
- NOT_FIT candidates were gate-rejected before LLM scoring; their LLM score separation is therefore unavailable.
- Retry-rate and token-cost fields were not persisted by the run, so they are not estimated.
- Exact hashing caught exact duplicates but not near duplicates.
- Webhook authentication defaulting to `none` is a finding, not a strength.

## Weaknesses found

1. Webhook authentication defaults to `none`; production configuration should require signature/auth verification.
2. There is no dead-letter stream for permanently failed worker messages.
3. Near-duplicate resumes are not caught by exact SHA-256 dedupe.
4. The authenticated API benchmark needs bounded login concurrency/timeouts and rerunning before any capacity claim.

## Resume-ready numbers

All values below are measured on 30 synthetic rows, two job profiles, local Windows venv, local PostgreSQL/Redis/Qdrant, Gemini embeddings, and Groq LLM routing:

- **468 passed, 0 failed** backend tests; **76%** full-suite line coverage.
- **1.000000** retrieval Hit@5 and **1.000000** retrieval Recall@10.
- **1.000000** nDCG@5 and nDCG@10 for each of the two synthetic job profiles.
- **0.879883** Spearman correlation on the 22 LLM-scored rows.
- **1.000000** adaptive-gate recall for STRONG_FIT (12/12).
- **0.000000** false-shortlist rate and **0.000000** false-reject rate on this synthetic set.
- **1.000000** first-try valid-JSON rate across 82 recorded provider attempts.
- **3.866311 resumes/minute** sequential end-to-end throughput.
- Pipeline latency: **17,095.448 ms p50** and **19,276.228 ms p95** per resume.
- **1.000000** decision agreement across 10 resumes evaluated three times each.

These are benchmark results, not a measured production capacity claim. The requested “5,000 requests/minute under 200 ms” result is **N/A** because the authenticated API run timed out before valid 200-response samples were collected.
