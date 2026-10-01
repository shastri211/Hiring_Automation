# Resume Screener

A multi-tenant hiring tool. Companies sign up, post jobs, and collect resumes
by bulk upload (PDF, DOCX or ZIP) or a public apply link. Resumes are
profiled, embedded and ranked semantically against each job. The best
matches get an LLM evaluation (SHORTLIST / REVIEW / REJECT), and shortlisted
candidates can be sent emails and browser-based voice interviews.

## How it works

1. **Job setup** - an LLM turns the job description into a structured profile.
2. **Resume processing** (Redis Streams worker): text extraction (OCR for
   image-only PDF pages) -> local deterministic profiling, with LLM
   profiling only as a fallback for weak extractions -> candidate identity
   resolution (duplicates are detected and can be merged) -> embedding into
   Qdrant.
3. **Screening** (on demand): semantic ranking plus an adaptive gate. Only
   candidates who pass the gate get an LLM evaluation; the rest are
   `PRE_SCREENED_OUT` with their semantic score kept.
4. **Follow-up**: HR decisions with an audit trail, email templates and bulk
   outreach, voice interviews (Dograh), talent pool and analytics.

| Layer | Technology |
|---|---|
| API | FastAPI (`app/`), SQLAlchemy async, Alembic migrations |
| Worker | `app/worker.py`, Redis Streams consumer group |
| Database | PostgreSQL 16 |
| Vectors | Qdrant Cloud |
| LLMs | Groq / Gemini / OpenRouter / NVIDIA with automatic fallback |
| Embeddings | Gemini, with a local sentence-transformers fallback |
| Frontend | React + Vite + TanStack Query (`frontend/`) |

## Local development

Prerequisites: Docker, Python 3.13, Node 22.

```bash
cp backend/.env.example backend/.env   # then fill in the values (see below)
docker compose up -d                   # Postgres + Redis
cd backend
python -m venv venv && venv\Scripts\activate   # macOS/Linux: source venv/bin/activate
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-dev.txt
alembic upgrade head
python -m scripts.create_user --platform-admin   # first account (interactive)
```

Run the three processes (the API on port 8001 matches the Vite dev proxy):

```bash
uvicorn app.main:app --port 8001
python -m app.worker
npm --prefix frontend install && npm --prefix frontend run dev
```

Open http://localhost:5173. Companies can also sign up at `/signup`.

### Configuration

Everything is set in `.env`; `.env.example` documents every setting. The
essentials:

- `POSTGRES_PASSWORD`, `SECRET_KEY` (a long random value outside local dev)
- `QDRANT_URL`, `QDRANT_API_KEY` - your Qdrant Cloud cluster
- At least one LLM key (`GROQ_API_KEY`, `GEMINI_API_KEY`, ...).
  `GEMINI_API_KEY` also enables OCR and the Gemini embedding profile.
- `PUBLIC_APP_BASE_URL` - builds verification, password-reset, apply and
  interview links
- `SMTP_*` - optional. Without `SMTP_HOST`, emails are simulated and shown as
  "Not delivered (no SMTP)".
- `DOGRAH_*` - optional voice interviews. Set `DOGRAH_WEBHOOK_AUTH_TYPE` and
  `DOGRAH_WEBHOOK_SECRET` before exposing the webhooks.
- `COOKIE_SECURE=True` once served over HTTPS.

## Tests

The suite never touches your data: it uses a separate Postgres schema
(`test_isolation`) and a separate Redis database (15), and mocks every
LLM/embedding provider. Create the schema once:

```bash
docker compose exec postgres psql -U screener -d resume_screener -c "CREATE SCHEMA IF NOT EXISTS test_isolation"
DB_SCHEMA=test_isolation alembic upgrade head
pytest -q
```

Frontend checks: `npm --prefix frontend run lint` and `npm --prefix frontend run build`.
CI (`.github/workflows/ci.yml`) runs both on every push to `main` and every pull request.

## Running everything in containers

```bash
docker compose --profile app up -d --build
```

This runs migrations, the API, the worker and an nginx-served frontend on
http://localhost:8080 (the API is reachable only through nginx at `/api`).
The containers read the same `.env`. Postgres and Redis are addressed by
their service names automatically.

## Project layout

```
backend/app/api/          HTTP routes (thin - business logic lives in backend/app/services/)
backend/app/services/     pipeline, screening, identity, email, interviews, tenancy
backend/app/models/       SQLAlchemy models        backend/alembic/versions/  migrations
backend/app/worker.py     queue consumer + recovery sweeps
frontend/src/  pages, components, API clients, hooks
backend/scripts/          operator tools (create_user, one-time backfill)
backend/tests/            pytest suite
```
