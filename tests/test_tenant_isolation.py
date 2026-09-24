"""Multi-tenancy Phase 2: cross-organization isolation.

Two organizations, A and B, each with a full data graph (job, batch,
resume, profile, candidates, match suggestion, application, screening
result, interview, template, email message, talent-pool entry, public
submission). Everything runs as a real logged-in user of one organization
against the real test-schema Postgres; external providers are mocked.

What establishes correctness here is behavior - every route's identifier
inputs (path, query, JSON body, form), every list/aggregate, and every
background/service path. The static grep test at the bottom is only a
regression detector for new unscoped queries.
"""
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.deps import get_authenticated_user, get_current_user
from app.db.session import AsyncSessionLocal
from app.models.application import Application
from app.models.batch import ScreeningBatch
from app.models.candidate import Candidate, CandidateMatchSuggestion
from app.models.email import EmailMessage, EmailTemplate
from app.models.interview import Interview
from app.models.job import Job
from app.models.organization import Organization
from app.models.profile import CandidateProfile
from app.models.public_application import PublicApplicationSubmission
from app.models.resume import Resume
from app.models.screening import ScreeningResult
from app.models.settings import AppSettings
from app.models.talent_pool import TalentPoolEntry
from app.models.user import User
from app.services.auth import hash_password

PASSWORD = "isolation-pass-1"


@pytest.fixture(autouse=True)
def _use_real_auth():
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_authenticated_user, None)
    yield


@pytest.fixture(autouse=True)
def _no_external_side_effects():
    """Any cross-tenant call that wrongly got past its org check must not
    reach Redis/Dograh/providers - these would surface as failures anyway."""
    with patch("app.services.queue.queue_service.enqueue_task", new_callable=AsyncMock), \
         patch("app.services.queue.queue_service.enqueue_resume", new_callable=AsyncMock):
        yield


# -- data graph ---------------------------------------------------------------------

async def _build_org(label: str) -> dict:
    """One organization's full graph, committed. Returns plain ids/values."""
    async with AsyncSessionLocal() as db:
        org = Organization(name=f"Org {label} {uuid.uuid4().hex[:4]}")
        db.add(org)
        await db.flush()
        admin = User(
            organization_id=org.id, email=f"admin-{label.lower()}-{uuid.uuid4().hex[:8]}@iso.test",
            name=f"Admin {label}", hashed_password=hash_password(PASSWORD), role="admin",
            email_verified_at=datetime.now(timezone.utc),
        )
        db.add(admin)
        db.add(AppSettings(organization_id=org.id))
        job = Job(
            organization_id=org.id, title=f"Job {label}", description="d",
            job_profile={"title": f"Job {label}"}, application_token=secrets.token_urlsafe(32),
        )
        db.add(job)
        await db.flush()
        batch = ScreeningBatch(job_id=job.id, total_resumes=1, status="COMPLETED")
        db.add(batch)
        await db.flush()
        cand = Candidate(organization_id=org.id, canonical_name=f"Cand {label}",
                         primary_email=f"shared-person-{label.lower()}@example.com", primary_phone="5550001111")
        cand2 = Candidate(organization_id=org.id, canonical_name=f"Cand2 {label}")
        db.add_all([cand, cand2])
        await db.flush()
        resume = Resume(
            job_id=job.id, batch_id=batch.id, candidate_id=cand.id, filename=f"{label}.pdf",
            file_hash=secrets.token_hex(16), storage_key=f"iso/{label}.pdf", status="READY",
            workflow_stage="EMBEDDED", extracted_text=f"Resume text {label}",
        )
        db.add(resume)
        await db.flush()
        db.add(CandidateProfile(resume_id=resume.id, name=f"Person {label}", email=cand.primary_email,
                                extraction_method="LLM_ENRICHED"))
        suggestion = CandidateMatchSuggestion(resume_id=resume.id, candidate_a_id=cand.id, candidate_b_id=cand2.id,
                                              confidence=0.6, signals={"phone_match": True}, status="PENDING")
        db.add(suggestion)
        application = Application(candidate_id=cand.id, job_id=job.id, current_resume_id=resume.id, batch_id=batch.id)
        db.add(application)
        await db.flush()
        db.add(ScreeningResult(job_id=job.id, resume_id=resume.id, application_id=application.id,
                               score=50.0, semantic_score=0.5, decision="REVIEW"))
        interview = Interview(job_id=job.id, resume_id=resume.id, status="SCHEDULED", provider="dograh",
                              public_token=secrets.token_urlsafe(32),
                              link_expires_at=datetime.now(timezone.utc) + timedelta(days=1))
        db.add(interview)
        template = EmailTemplate(organization_id=org.id, name=f"Template {label}", subject="Hi", body_content="Body")
        db.add(template)
        await db.flush()
        db.add(EmailMessage(job_id=job.id, resume_id=resume.id, template_id=template.id, subject="Hi",
                            body_content="Body", status="SENT"))
        entry = TalentPoolEntry(organization_id=org.id, resume_id=resume.id, added_from_job_id=job.id,
                                tags=["t"], notes="n")
        db.add(entry)
        db.add(PublicApplicationSubmission(resume_id=resume.id, job_id=job.id, applicant_name=f"Applicant {label}",
                                           applicant_email=f"applicant-{label.lower()}@example.com",
                                           consent_at=datetime.now(timezone.utc)))
        await db.flush()
        await db.commit()
        return {
            "org": org.id, "admin_email": admin.email, "admin_id": admin.id, "job": job.id, "batch": batch.id,
            "resume": resume.id, "candidate": cand.id, "candidate2": cand2.id, "suggestion": suggestion.id,
            "interview": interview.id, "interview_token": interview.public_token,
            "application_token": job.application_token, "template": template.id, "entry": entry.id,
            "application": application.id,
        }


@pytest.fixture(scope="module")
async def graph():
    return {"A": await _build_org("A"), "B": await _build_org("B")}


def _client():
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _login_as(client: AsyncClient, org: dict) -> AsyncClient:
    res = await client.post("/auth/login", json={"email": org["admin_email"], "password": PASSWORD})
    assert res.status_code == 200, res.text
    return client


async def _snapshot(g: dict) -> dict:
    """Every mutable value of both organizations' graphs."""
    async with AsyncSessionLocal() as db:
        snap = {}
        for label, o in g.items():
            job = (await db.execute(select(Job).where(Job.id == o["job"]))).scalar_one()
            resume = (await db.execute(select(Resume).where(Resume.id == o["resume"]))).scalar_one()
            cands = (await db.execute(select(Candidate).where(Candidate.id.in_([o["candidate"], o["candidate2"]])))).scalars().all()
            sugg = (await db.execute(select(CandidateMatchSuggestion).where(CandidateMatchSuggestion.id == o["suggestion"]))).scalar_one()
            sr = (await db.execute(select(ScreeningResult).where(ScreeningResult.resume_id == o["resume"]))).scalars().all()
            iv = (await db.execute(select(Interview).where(Interview.id == o["interview"]))).scalar_one()
            tpl = (await db.execute(select(EmailTemplate).where(EmailTemplate.id == o["template"]))).scalar_one()
            msgs = (await db.execute(select(EmailMessage).where(EmailMessage.job_id == o["job"]))).scalars().all()
            entry = (await db.execute(select(TalentPoolEntry).where(TalentPoolEntry.id == o["entry"]))).scalar_one_or_none()
            batches = (await db.execute(select(func.count(ScreeningBatch.id)).where(ScreeningBatch.job_id == o["job"]))).scalar_one()
            resumes = (await db.execute(select(func.count(Resume.id)).where(Resume.job_id == o["job"]))).scalar_one()
            settings_row = (await db.execute(select(AppSettings).where(AppSettings.organization_id == o["org"]))).scalar_one()
            snap[label] = {
                "job": (job.status, job.application_token, job.title, job.embedding_status),
                "resume": (resume.status, resume.candidate_id, resume.workflow_stage),
                "candidates": sorted((c.id, c.canonical_name, c.merged_into_id) for c in cands),
                "suggestion": (sugg.status, sugg.reviewed_by),
                "screening": sorted((s.decision, s.score, s.notes) for s in sr),
                "interview": (iv.status, iv.retry_count, iv.public_token, iv.outcome),
                "template": (tpl.name, tpl.subject, tpl.body_content),
                "messages": sorted((m.status, m.template_id) for m in msgs),
                "entry": (entry.tags, entry.notes) if entry else None,
                "batches": batches,
                "resumes": resumes,
                "settings": (settings_row.min_candidates_to_screen, settings_row.shortlist_email_template_id,
                             settings_row.email_test_override_recipient),
            }
        return snap


# -- route coverage: every identifier input -------------------------------------------------
#
# Each case: called as B with A's identifier(s) (or a mix), must return one of
# the expected statuses. Keys are (METHOD, path template) exactly as FastAPI
# reports them; test_every_authenticated_route_is_classified fails if an
# authenticated route is in neither CROSS_TENANT_CASES nor NO_IDENTIFIER_INPUT.

NF = {404}

CROSS_TENANT_CASES = {
    ("PATCH", "/auth/users/{user_id}"): [lambda a, b: ("PATCH", f"/auth/users/{a['admin_id']}", {"json": {"is_active": False}}, NF)],
    ("GET", "/jobs/{job_id}"): [lambda a, b: ("GET", f"/jobs/{a['job']}", {}, NF)],
    ("POST", "/jobs/{job_id}/pause"): [lambda a, b: ("POST", f"/jobs/{a['job']}/pause", {}, NF)],
    ("POST", "/jobs/{job_id}/resume"): [lambda a, b: ("POST", f"/jobs/{a['job']}/resume", {}, NF)],
    ("POST", "/jobs/{job_id}/archive"): [lambda a, b: ("POST", f"/jobs/{a['job']}/archive", {}, NF)],
    ("POST", "/jobs/{job_id}/application-link"): [lambda a, b: ("POST", f"/jobs/{a['job']}/application-link", {}, NF)],
    ("POST", "/jobs/{job_id}/application-link/rotate"): [lambda a, b: ("POST", f"/jobs/{a['job']}/application-link/rotate", {}, NF)],
    ("DELETE", "/jobs/{job_id}/application-link"): [lambda a, b: ("DELETE", f"/jobs/{a['job']}/application-link", {}, NF)],
    ("DELETE", "/jobs/{job_id}"): [lambda a, b: ("DELETE", f"/jobs/{a['job']}", {}, NF)],
    ("POST", "/jobs/{job_id}/screen"): [lambda a, b: ("POST", f"/jobs/{a['job']}/screen", {}, NF)],
    ("POST", "/jobs/{job_id}/migrate-embedding-profile"): [lambda a, b: ("POST", f"/jobs/{a['job']}/migrate-embedding-profile", {}, NF)],
    ("GET", "/jobs/{job_id}/results"): [lambda a, b: ("GET", f"/jobs/{a['job']}/results", {}, NF)],
    ("GET", "/jobs/{job_id}/results/{resume_id}"): [
        lambda a, b: ("GET", f"/jobs/{a['job']}/results/{a['resume']}", {}, NF),
        lambda a, b: ("GET", f"/jobs/{b['job']}/results/{a['resume']}", {}, NF),  # own job, foreign resume
    ],
    ("POST", "/jobs/{job_id}/interviews/{resume_id}/resync"): [
        lambda a, b: ("POST", f"/jobs/{a['job']}/interviews/{a['resume']}/resync", {}, NF),
        lambda a, b: ("POST", f"/jobs/{b['job']}/interviews/{a['resume']}/resync", {}, NF),
    ],
    ("POST", "/jobs/{job_id}/interviews/{resume_id}/decline"): [
        lambda a, b: ("POST", f"/jobs/{a['job']}/interviews/{a['resume']}/decline", {}, NF),
        lambda a, b: ("POST", f"/jobs/{b['job']}/interviews/{a['resume']}/decline", {}, NF),
    ],
    ("PATCH", "/jobs/{job_id}/results/{resume_id}/decision"): [
        lambda a, b: ("PATCH", f"/jobs/{a['job']}/results/{a['resume']}/decision", {"json": {"decision": "REJECT"}}, NF),
        lambda a, b: ("PATCH", f"/jobs/{b['job']}/results/{a['resume']}/decision", {"json": {"decision": "REJECT"}}, NF),
    ],
    ("POST", "/jobs/{job_id}/results/{resume_id}/retry-evaluation"): [
        lambda a, b: ("POST", f"/jobs/{a['job']}/results/{a['resume']}/retry-evaluation", {}, NF),
        lambda a, b: ("POST", f"/jobs/{b['job']}/results/{a['resume']}/retry-evaluation", {}, NF),
    ],
    ("PATCH", "/jobs/{job_id}/results/bulk-decision"): [
        lambda a, b: ("PATCH", f"/jobs/{a['job']}/results/bulk-decision", {"json": {"resume_ids": [a["resume"]], "decision": "REJECT"}}, NF),
        # own job, body with foreign / mixed resume ids -> whole request refused
        lambda a, b: ("PATCH", f"/jobs/{b['job']}/results/bulk-decision", {"json": {"resume_ids": [a["resume"]], "decision": "REJECT"}}, {422}),
        lambda a, b: ("PATCH", f"/jobs/{b['job']}/results/bulk-decision", {"json": {"resume_ids": [b["resume"], a["resume"]], "decision": "REJECT"}}, {422}),
    ],
    ("GET", "/jobs/{job_id}/progress"): [lambda a, b: ("GET", f"/jobs/{a['job']}/progress", {}, NF)],
    ("POST", "/resumes/upload/{job_id}"): [
        lambda a, b: ("POST", f"/resumes/upload/{a['job']}", {"files": {"files": ("x.pdf", b"%PDF x " + secrets.token_bytes(8), "application/pdf")}}, NF),
    ],
    ("GET", "/resumes/file/{resume_id}"): [lambda a, b: ("GET", f"/resumes/file/{a['resume']}", {}, NF)],
    ("POST", "/integration/interview/trigger"): [
        lambda a, b: ("POST", "/integration/interview/trigger", {"json": {"job_id": a["job"], "resume_id": a["resume"]}}, NF),
        lambda a, b: ("POST", "/integration/interview/trigger", {"json": {"job_id": b["job"], "resume_id": a["resume"]}}, NF),
    ],
    ("PATCH", "/candidates/{candidate_id}"): [lambda a, b: ("PATCH", f"/candidates/{a['candidate']}", {"json": {"canonical_name": "Hijacked"}}, NF)],
    ("GET", "/candidates/{candidate_id}"): [lambda a, b: ("GET", f"/candidates/{a['candidate']}", {}, NF)],
    ("POST", "/candidates/match-suggestions/{suggestion_id}/merge"): [lambda a, b: ("POST", f"/candidates/match-suggestions/{a['suggestion']}/merge", {}, NF)],
    ("POST", "/candidates/match-suggestions/{suggestion_id}/reject"): [lambda a, b: ("POST", f"/candidates/match-suggestions/{a['suggestion']}/reject", {}, NF)],
    ("POST", "/candidates/merge"): [
        lambda a, b: ("POST", "/candidates/merge", {"json": {"absorbed_candidate_id": a["candidate2"], "into_candidate_id": a["candidate"]}}, NF),
        lambda a, b: ("POST", "/candidates/merge", {"json": {"absorbed_candidate_id": b["candidate2"], "into_candidate_id": a["candidate"]}}, NF),
    ],
    ("POST", "/candidates/{candidate_id}/unmerge"): [lambda a, b: ("POST", f"/candidates/{a['candidate2']}/unmerge", {}, NF)],
    ("PATCH", "/emails/templates/{template_id}"): [lambda a, b: ("PATCH", f"/emails/templates/{a['template']}", {"json": {"subject": "Hijacked"}}, NF)],
    ("DELETE", "/emails/templates/{template_id}"): [lambda a, b: ("DELETE", f"/emails/templates/{a['template']}", {}, NF)],
    ("POST", "/emails/jobs/{job_id}/bulk-send"): [
        lambda a, b: ("POST", f"/emails/jobs/{a['job']}/bulk-send", {"json": {"resume_ids": [a["resume"]], "template_id": a["template"]}}, NF),
        lambda a, b: ("POST", f"/emails/jobs/{b['job']}/bulk-send", {"json": {"resume_ids": [b["resume"]], "template_id": a["template"]}}, NF),
        lambda a, b: ("POST", f"/emails/jobs/{b['job']}/bulk-send", {"json": {"resume_ids": [a["resume"]], "template_id": b["template"]}}, {422}),
    ],
    ("GET", "/emails/messages"): [lambda a, b: ("GET", "/emails/messages", {"params": {"job_id": a["job"]}}, NF)],
    ("GET", "/emails/candidates/{resume_id}"): [lambda a, b: ("GET", f"/emails/candidates/{a['resume']}", {}, NF)],
    # Phase 1 contract kept: an unusable template id is a 400 validation error.
    ("PATCH", "/settings/"): [
        lambda a, b: ("PATCH", "/settings/", {"json": {"shortlist_email_template_id": a["template"]}}, {400}),
        lambda a, b: ("PATCH", "/settings/", {"json": {"interview_scheduled_email_template_id": a["template"]}}, {400}),
    ],
    ("POST", "/talent-pool/"): [
        lambda a, b: ("POST", "/talent-pool/", {"json": {"resume_id": a["resume"]}}, NF),
    ],
    ("PATCH", "/talent-pool/{entry_id}"): [lambda a, b: ("PATCH", f"/talent-pool/{a['entry']}", {"json": {"notes": "Hijacked"}}, NF)],
    ("DELETE", "/talent-pool/{entry_id}"): [lambda a, b: ("DELETE", f"/talent-pool/{a['entry']}", {}, NF)],
    ("GET", "/interviews/"): [lambda a, b: ("GET", "/interviews/", {"params": {"job_id": a["job"]}}, NF)],
    ("GET", "/interview-analysis/summary"): [lambda a, b: ("GET", "/interview-analysis/summary", {"params": {"job_id": a["job"]}}, NF)],
    ("GET", "/interview-analysis/"): [lambda a, b: ("GET", "/interview-analysis/", {"params": {"job_id": a["job"]}}, NF)],
    ("GET", "/analytics/funnel"): [lambda a, b: ("GET", "/analytics/funnel", {"params": {"job_id": a["job"]}}, NF)],
    ("GET", "/analytics/decisions"): [lambda a, b: ("GET", "/analytics/decisions", {"params": {"job_id": a["job"]}}, NF)],
    ("GET", "/analytics/throughput"): [lambda a, b: ("GET", "/analytics/throughput", {"params": {"job_id": a["job"]}}, NF)],
    ("GET", "/analytics/time-in-stage"): [lambda a, b: ("GET", "/analytics/time-in-stage", {"params": {"job_id": a["job"]}}, NF)],
}

# Authenticated routes that take no object identifier at all (own data /
# creation / platform-level). Lists among them are covered by
# test_lists_and_aggregates_never_include_another_organization.
NO_IDENTIFIER_INPUT = {
    ("GET", "/auth/me"), ("POST", "/auth/change-password"),
    ("POST", "/auth/users"), ("GET", "/auth/users"),
    ("GET", "/jobs/"), ("GET", "/jobs/batches/overview"), ("POST", "/jobs/"), ("POST", "/jobs/upload"),
    ("GET", "/candidates/"), ("GET", "/candidates/match-suggestions"),
    ("POST", "/emails/templates"), ("GET", "/emails/templates"),
    ("GET", "/settings/"),
    ("GET", "/talent-pool/"),
    ("GET", "/analytics/job-volume"),
    # Platform-level (shared provider config), platform-admin only - see
    # test_tenancy_phase1.py::test_integrations_are_platform_admin_only.
    ("GET", "/integrations/"), ("POST", "/integrations/{provider}/test"),
}

# Not HR-session routes: public/token or webhook-authenticated. Token
# surfaces are covered by the public-token tests below.
NOT_HR_AUTHENTICATED = {
    ("GET", "/health"), ("POST", "/auth/login"), ("POST", "/auth/logout"), ("POST", "/auth/signup"),
    ("POST", "/auth/verify-email"), ("POST", "/auth/resend-verification"),
    ("POST", "/integration/interview/status"), ("POST", "/integration/interview/transcript"),
    ("POST", "/integration/interview/evaluation"),
    ("GET", "/public/interview/{token}"), ("POST", "/public/interview/{token}/started"),
    ("GET", "/public/jobs/{token}"), ("POST", "/public/jobs/{token}/apply"),
}


def _dependency_calls(dependant) -> set:
    calls = set()
    for dep in dependant.dependencies:
        if dep.call is not None:
            calls.add(dep.call)
        calls |= _dependency_calls(dep)
    return calls


def _all_routes():
    from fastapi.routing import iter_route_contexts
    from app.main import app

    for ctx in iter_route_contexts(app.router.routes):
        effective = getattr(ctx, "_effective_route", None) or ctx.route
        dependant = getattr(effective, "dependant", None)
        if dependant is None or not ctx.methods:
            continue
        for method in ctx.methods:
            yield method, ctx.path, get_authenticated_user in _dependency_calls(dependant)


def test_every_route_is_classified_for_tenant_isolation():
    """A new route can't ship without a cross-tenant case (or an explicit
    classification). Public routes must stay unauthenticated and vice versa."""
    routes = list(_all_routes())
    assert len(routes) > 60
    unclassified, misclassified = [], []
    for method, path, authenticated in routes:
        key = (method, path)
        if authenticated:
            if key not in CROSS_TENANT_CASES and key not in NO_IDENTIFIER_INPUT:
                unclassified.append(key)
            if key in NOT_HR_AUTHENTICATED:
                misclassified.append(key)
        elif key not in NOT_HR_AUTHENTICATED:
            misclassified.append(key)
    assert not unclassified, f"Authenticated routes with no tenant-isolation case: {unclassified}"
    assert not misclassified, f"Routes whose auth doesn't match their classification: {misclassified}"
    # No stale entries either.
    known = {(m, p) for m, p, _ in routes}
    assert set(CROSS_TENANT_CASES) <= known
    assert NO_IDENTIFIER_INPUT <= known


async def test_cross_tenant_identifier_inputs_are_rejected_and_write_nothing(graph):
    a, b = graph["A"], graph["B"]
    before = await _snapshot(graph)

    failures = []
    async with _client() as client:
        await _login_as(client, b)
        for key, cases in CROSS_TENANT_CASES.items():
            for build in cases:
                method, url, kwargs, expected = build(a, b)
                res = await client.request(method, url, **kwargs)
                if res.status_code not in expected:
                    failures.append((key, url, kwargs.get("json") or kwargs.get("params"), res.status_code, res.text[:200]))

    assert not failures, "Cross-tenant requests not rejected:\n" + "\n".join(map(str, failures))
    assert await _snapshot(graph) == before, "A cross-tenant request changed data"


async def test_lists_and_aggregates_never_include_another_organization(graph):
    a, b = graph["A"], graph["B"]

    async with _client() as client:
        await _login_as(client, b)

        async def ids(url, key="id", items="items", **params):
            body = (await client.get(url, params=params)).json()
            rows = body[items] if items and isinstance(body, dict) else body
            return {r[key] for r in rows}

        assert a["job"] not in await ids("/jobs/", items=None)
        assert b["job"] in await ids("/jobs/", items=None)
        assert a["job"] not in await ids("/jobs/batches/overview", key="job_id", items=None)
        assert b["job"] in await ids("/jobs/batches/overview", key="job_id", items=None)
        cand_rows = await ids("/candidates/", key="resume_id", page_size=100)
        assert a["resume"] not in cand_rows and b["resume"] in cand_rows
        sugg = await ids("/candidates/match-suggestions", items=None)
        assert a["suggestion"] not in sugg and b["suggestion"] in sugg
        tpls = await ids("/emails/templates", items=None)
        assert a["template"] not in tpls and b["template"] in tpls
        msg_jobs = await ids("/emails/messages", key="job_id", page_size=100)
        assert a["job"] not in msg_jobs and b["job"] in msg_jobs
        pool = await ids("/talent-pool/", page_size=100)
        assert a["entry"] not in pool and b["entry"] in pool
        ivs = await ids("/interviews/", page_size=100)
        assert a["interview"] not in ivs and b["interview"] in ivs
        analysed = await ids("/interview-analysis/", key="job_id", page_size=100)
        assert a["job"] not in analysed and b["job"] in analysed
        vol = await ids("/analytics/job-volume", key="job_id")
        assert a["job"] not in vol and b["job"] in vol
        users = await ids("/auth/users", key="email", items=None)
        assert a["admin_email"] not in users and b["admin_email"] in users

        # Aggregates are B-only: exactly B's own one-resume graph.
        funnel = (await client.get("/analytics/funnel")).json()
        assert funnel["uploaded"] == 1 and funnel["screened"] == 1 and funnel["interviewed"] == 1
        decisions = (await client.get("/analytics/decisions")).json()
        assert decisions["total"] == 1
        summary = (await client.get("/interview-analysis/summary")).json()
        assert summary["total_interviews"] == 1
        # A job_id filter on B's own job still works.
        assert (await client.get("/analytics/funnel", params={"job_id": b["job"]})).json()["uploaded"] == 1


# -- background / service paths (the actual correctness mechanism) ----------------------------

def _orchestrator_mocks(extracted_email: str, phone: str | None = None):
    extractor = AsyncMock()
    extractor.extract.return_value = f"Some Person\n{extracted_email}\nPython engineer"
    return extractor, [
        patch("app.services.orchestrator.get_extractor", return_value=extractor),
        patch("app.services.orchestrator.LocalProfilerService.profile_candidate", return_value=(
            {"name": "Some Person", "contact": {"email": extracted_email, "phone": phone}, "skills": ["python"]},
            "canonical text", {"is_insufficient": False},
        )),
        patch("app.services.orchestrator.profiler_service.profile_candidate", new_callable=AsyncMock),
        patch("app.services.orchestrator.embedding_router.generate_embedding", new_callable=AsyncMock,
              return_value=([0.1, 0.2], MagicMock(collection="iso", dimensions=2, metric="Cosine"))),
        patch("app.services.orchestrator.vector_store.create_collection", new_callable=AsyncMock),
        patch("app.services.orchestrator.vector_store.add_points", new_callable=AsyncMock),
    ]


async def _new_uploaded_resume(org: dict, *, file_hash: str | None = None, job_id: int | None = None) -> int:
    async with AsyncSessionLocal() as db:
        jid = job_id or org["job"]
        batch = ScreeningBatch(job_id=jid, total_resumes=1)
        db.add(batch)
        await db.flush()
        resume = Resume(job_id=jid, batch_id=batch.id, filename="new.pdf", file_hash=file_hash or secrets.token_hex(16),
                        storage_key="iso/new.pdf", status="UPLOADED", workflow_stage="UPLOADED")
        db.add(resume)
        await db.commit()
        return resume.id


async def _process(resume_id: int, email: str, phone: str | None = None):
    from app.services.orchestrator import orchestrator

    extractor, mocks = _orchestrator_mocks(email, phone)
    started = [m.start() for m in mocks]
    try:
        await orchestrator.process_candidate(resume_id)
    finally:
        for m in mocks:
            m.stop()
    return extractor, started


async def test_identity_never_links_or_suggests_across_organizations(graph):
    a, b = graph["A"], graph["B"]
    async with AsyncSessionLocal() as db:
        a_email = (await db.execute(select(Candidate.primary_email).where(Candidate.id == a["candidate"]))).scalar_one()

    # B receives a resume with A's candidate's email and phone.
    resume_id = await _new_uploaded_resume(b)
    await _process(resume_id, a_email, phone="5550001111")

    async with AsyncSessionLocal() as db:
        resume = (await db.execute(select(Resume).where(Resume.id == resume_id))).scalar_one()
        assert resume.status == "READY"
        cand = (await db.execute(select(Candidate).where(Candidate.id == resume.candidate_id))).scalar_one()
        assert cand.organization_id == b["org"]
        assert cand.id != a["candidate"]
        # Phone match suggestion, if any, only pairs B's candidates.
        suggestions = (await db.execute(
            select(CandidateMatchSuggestion).where(CandidateMatchSuggestion.resume_id == resume_id)
        )).scalars().all()
        for s in suggestions:
            orgs = set((await db.execute(select(Candidate.organization_id).where(
                Candidate.id.in_([s.candidate_a_id, s.candidate_b_id])))).scalars().all())
            assert orgs == {b["org"]}
        # A's candidate is untouched and still A's only.
        assert (await db.execute(select(func.count(Resume.id)).where(Resume.candidate_id == a["candidate"]))).scalar_one() == 1


async def test_resume_reuse_is_strictly_per_organization(graph):
    a, b = graph["A"], graph["B"]
    async with AsyncSessionLocal() as db:
        a_hash = (await db.execute(select(Resume.file_hash).where(Resume.id == a["resume"]))).scalar_one()
        second_a_job = Job(organization_id=a["org"], title="A second", description="d", job_profile={"title": "x"})
        db.add(second_a_job)
        await db.commit()
        second_a_job_id = second_a_job.id

    # Same bytes arrive in B: B extracts/profiles/embeds on its own.
    b_resume = await _new_uploaded_resume(b, file_hash=a_hash)
    extractor, started = await _process(b_resume, "someone@b.example")
    extractor.extract.assert_awaited_once()
    started[5].assert_awaited_once()  # add_points: its own embedding

    async with AsyncSessionLocal() as db:
        b_text = (await db.execute(select(Resume.extracted_text).where(Resume.id == b_resume))).scalar_one()
        assert b_text != "Resume text A"  # nothing copied from A

    # Same bytes to another A job: reuse still works within A.
    a2_resume = await _new_uploaded_resume(a, file_hash=a_hash, job_id=second_a_job_id)
    extractor, _ = await _process(a2_resume, "ignored@a.example")
    extractor.extract.assert_not_awaited()
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(Resume.extracted_text).where(Resume.id == a2_resume))).scalar_one() == "Resume text A"


async def test_screening_uses_the_jobs_own_organization_thresholds(graph):
    from app.services.screener import screener_service
    from app.services.settings import settings_service

    b = graph["B"]
    spy = AsyncMock(return_value=(5, 20, 0.05))
    async with AsyncSessionLocal() as db:
        job_b = (await db.execute(select(Job).where(Job.id == b["job"]))).scalar_one()
        with patch.object(settings_service, "get_effective_screening_config", spy), \
             patch("app.services.embeddings.embedding_router.generate_embedding", new_callable=AsyncMock,
                   return_value=([0.1, 0.2], MagicMock(collection="iso"))), \
             patch("app.services.screener.vector_store.search", new_callable=AsyncMock, return_value=[]):
            await screener_service.screen_job(db, job_b)
    spy.assert_awaited_once()
    assert spy.await_args.args[1] == b["org"]


async def test_outreach_uses_only_the_jobs_organization_settings(graph):
    from app.services.outreach import outreach_service

    a, b = graph["A"], graph["B"]
    async with AsyncSessionLocal() as db:
        sa = (await db.execute(select(AppSettings).where(AppSettings.organization_id == a["org"]))).scalar_one()
        sa.auto_email_on_shortlist = True
        sa.shortlist_email_template_id = a["template"]
        await db.commit()
    try:
        with patch("app.services.outreach.email_service.queue_bulk_emails", new_callable=AsyncMock) as queue:
            await outreach_service.on_decision_shortlisted(job_id=b["job"], resume_ids=[b["resume"]])
            queue.assert_not_awaited()  # B hasn't enabled it; A's toggle must not apply
            await outreach_service.on_decision_shortlisted(job_id=a["job"], resume_ids=[a["resume"]])
            queue.assert_awaited_once()
            assert queue.await_args.kwargs["template_id"] == a["template"]
    finally:
        async with AsyncSessionLocal() as db:
            sa = (await db.execute(select(AppSettings).where(AppSettings.organization_id == a["org"]))).scalar_one()
            sa.auto_email_on_shortlist = False
            sa.shortlist_email_template_id = None
            await db.commit()


async def test_send_time_overrides_and_allowlist_are_the_messages_organization(graph):
    from app.services.email import email_service

    a, b = graph["A"], graph["B"]
    async with AsyncSessionLocal() as db:
        b_email = (await db.execute(select(CandidateProfile.email).where(CandidateProfile.resume_id == b["resume"]))).scalar_one()
        sa = (await db.execute(select(AppSettings).where(AppSettings.organization_id == a["org"]))).scalar_one()
        sa.email_test_override_recipient = "a-override@example.com"
        sa.email_test_allowlist = b_email  # would let B's candidate through if (wrongly) applied to B
        tpl2 = EmailTemplate(organization_id=b["org"], name=f"B send {uuid.uuid4().hex[:4]}", subject="s", body_content="b")
        db.add(tpl2)
        await db.flush()
        msg = EmailMessage(job_id=b["job"], resume_id=b["resume"], template_id=tpl2.id, subject="s",
                           body_content="b", status="PENDING")
        db.add(msg)
        await db.commit()
        msg_id = msg.id
    try:
        with patch.object(email_service.provider, "send_email", new_callable=AsyncMock) as send:
            await email_service.process_send_email_task(msg_id)
            send.assert_not_awaited()  # B has no allowlist entry -> blocked; A's override not used
        async with AsyncSessionLocal() as db:
            status = (await db.execute(select(EmailMessage.status).where(EmailMessage.id == msg_id))).scalar_one()
            assert status == "BLOCKED"
    finally:
        async with AsyncSessionLocal() as db:
            sa = (await db.execute(select(AppSettings).where(AppSettings.organization_id == a["org"]))).scalar_one()
            sa.email_test_override_recipient = None
            sa.email_test_allowlist = None
            await db.commit()


async def test_queue_bulk_emails_refuses_another_organizations_template_and_resumes(graph):
    from app.services.email import email_service
    from app.services.queue import queue_service

    a, b = graph["A"], graph["B"]
    with pytest.raises(ValueError):
        await email_service.queue_bulk_emails(
            job_id=b["job"], resume_ids=[b["resume"]], template_id=a["template"], queue_service=queue_service,
        )
    # B's own template, A's resume id: skipped, nothing created for it.
    async with AsyncSessionLocal() as db:
        tpl = EmailTemplate(organization_id=b["org"], name=f"B bulk {uuid.uuid4().hex[:4]}", subject="s", body_content="b")
        db.add(tpl)
        await db.commit()
        tpl_id = tpl.id
    queued = await email_service.queue_bulk_emails(
        job_id=b["job"], resume_ids=[a["resume"]], template_id=tpl_id, queue_service=queue_service,
    )
    assert queued == 0
    async with AsyncSessionLocal() as db:
        assert (await db.execute(select(func.count(EmailMessage.id)).where(EmailMessage.template_id == tpl_id))).scalar_one() == 0


async def test_qdrant_search_and_delete_stay_within_the_job(graph):
    """Real in-memory Qdrant: A's and B's points share one collection; B's
    screening only ever retrieves B's job's points, and deleting A's job
    leaves B's points."""
    from qdrant_client import AsyncQdrantClient
    from app.services.screener import screener_service
    from app.services.vector_store import vector_store

    a, b = graph["A"], graph["B"]
    collection = f"iso_{uuid.uuid4().hex[:8]}"
    client = AsyncQdrantClient(location=":memory:")
    with patch.object(vector_store, "client", client):
        await vector_store.create_collection(collection, 2, "Cosine")
        await vector_store.add_points(
            collection, ids=[a["resume"], b["resume"]], vectors=[[0.9, 0.1], [0.1, 0.9]],
            payloads=[{"resume_id": a["resume"], "job_id": a["job"], "profile": {}},
                      {"resume_id": b["resume"], "job_id": b["job"], "profile": {}}],
        )

        hits = await vector_store.search(collection, [0.9, 0.1], limit=10, query_filter={"job_id": b["job"]})
        assert [p["resume_id"] for _, _, p in hits] == [b["resume"]]

        # Through screen_job itself: every retrieved candidate is B's.
        seen = []
        real_search = vector_store.search

        async def _spy_search(*args, **kwargs):
            results = await real_search(*args, **kwargs)
            seen.extend(p["resume_id"] for _, _, p in results)
            return results

        async with AsyncSessionLocal() as db:
            job_b = (await db.execute(select(Job).where(Job.id == b["job"]))).scalar_one()
            with patch("app.services.embeddings.embedding_router.generate_embedding", new_callable=AsyncMock,
                       return_value=([0.9, 0.1], MagicMock(collection=collection))), \
                 patch("app.services.screener.vector_store.search", side_effect=_spy_search), \
                 patch.object(screener_service, "evaluate_candidate", new_callable=AsyncMock,
                              return_value={"score": 80, "decision": "SHORTLIST", "strengths": [], "gaps": [], "evidence": []}), \
                 patch("app.services.outreach.outreach_service.on_decision_shortlisted", new_callable=AsyncMock):
                await screener_service.screen_job(db, job_b)
        assert seen == [b["resume"]]

        await vector_store.delete_points_by_filter(collection, {"job_id": a["job"]})
        remaining = await vector_store.search(collection, [0.1, 0.9], limit=10)
        assert [p["resume_id"] for _, _, p in remaining] == [b["resume"]]


# -- public token surfaces -----------------------------------------------------------------------

async def test_interview_token_only_exposes_its_own_organizations_data(graph):
    a, b = graph["A"], graph["B"]
    async with _client() as client:
        body_a = (await client.get(f"/public/interview/{a['interview_token']}")).json()
        assert body_a["initial_context"]["job_id"] == a["job"]
        assert body_a["initial_context"]["resume_id"] == a["resume"]
        assert body_a["job_title"] == "Job A" and body_a["candidate_name"] == "Person A"
        body_b = (await client.get(f"/public/interview/{b['interview_token']}")).json()
        assert body_b["initial_context"]["job_id"] == b["job"]

        # B's recruiter gains nothing about A's interview through their session.
        await _login_as(client, b)
        ivs = (await client.get("/interviews/", params={"page_size": 100})).json()["items"]
        assert a["interview"] not in {i["id"] for i in ivs}


async def test_application_token_writes_only_under_its_own_job_and_organization(graph, tmp_path):
    from app.services.storage import storage_service

    a, b = graph["A"], graph["B"]
    async with AsyncSessionLocal() as db:
        b_email = (await db.execute(select(Candidate.primary_email).where(Candidate.id == b["candidate"]))).scalar_one()

    with patch.object(storage_service, "base_dir", str(tmp_path)), \
         patch("app.api.public_application.rate_limit.check", new_callable=AsyncMock, return_value=(True, 1)), \
         patch("app.services.public_application.queue_service.enqueue_resume", new_callable=AsyncMock):
        async with _client() as client:
            res = await client.post(
                f"/public/jobs/{a['application_token']}/apply",
                data={"name": "Cross Applicant", "email": b_email, "consent": "true"},
                files={"file": ("cv.pdf", b"%PDF cross " + secrets.token_bytes(8), "application/pdf")},
            )
            assert res.status_code == 202

    async with AsyncSessionLocal() as db:
        sub = (await db.execute(
            select(PublicApplicationSubmission).where(PublicApplicationSubmission.applicant_name == "Cross Applicant")
        )).scalar_one()
        assert sub.job_id == a["job"]
        applied_resume = (await db.execute(select(Resume).where(Resume.id == sub.resume_id))).scalar_one()
        assert applied_resume.job_id == a["job"]

    # Processing it with B's candidate's email as the extracted email still
    # never links to B's candidate.
    await _process(applied_resume.id, b_email)
    async with AsyncSessionLocal() as db:
        cand_id = (await db.execute(select(Resume.candidate_id).where(Resume.id == applied_resume.id))).scalar_one()
        org_id = (await db.execute(select(Candidate.organization_id).where(Candidate.id == cand_id))).scalar_one()
        assert cand_id != b["candidate"] and org_id == a["org"]

    # B's recruiter can't open A's applicant (or its self-reported contact).
    async with _client() as client:
        await _login_as(client, b)
        assert (await client.get(f"/jobs/{a['job']}/results/{applied_resume.id}")).status_code == 404
        assert (await client.get(f"/jobs/{b['job']}/results/{applied_resume.id}")).status_code == 404


async def test_rotating_or_closing_one_organizations_link_never_affects_another(graph):
    a, b = graph["A"], graph["B"]
    async with _client() as client:
        await _login_as(client, b)
        assert (await client.post(f"/jobs/{b['job']}/application-link/rotate")).status_code == 200
        assert (await client.delete(f"/jobs/{b['job']}/application-link")).status_code == 200
        # A's link still resolves.
        assert (await client.get(f"/public/jobs/{a['application_token']}")).status_code == 200
        # Restore B's link for any later test in this module.
        reopened = (await client.post(f"/jobs/{b['job']}/application-link")).json()
        graph["B"]["application_token"] = reopened["application_token"]


# -- static regression detector (not a proof of correctness) ------------------------------------

# select(<RootModel>) calls in services/worker that need no organization
# predicate, each with the reason. Anything else must mention
# organization_id (or org_job_ids) in the same statement.
_STATIC_ALLOWLIST = {
    ("app/services/candidate_identity.py", "select(Candidate).where(Candidate.id == current_id)"): "id-keyed merge-chain hop (chain stays within one org)",
    ("app/services/candidate_identity.py", "select(Candidate).where(Candidate.id == canonical_absorbed_id)"): "id-keyed, org checked by _require_candidates_in_org",
    ("app/services/candidate_identity.py", "select(Candidate).where(Candidate.id == absorbed_id)"): "id-keyed, org checked by _require_candidates_in_org",
    ("app/services/candidate_identity.py", "select(Candidate.id).where(Candidate.id.in_(lock_ids))"): "row lock after org check",
    ("app/services/orchestrator.py", "select(Job).where(Job.id == resume.job_id)"): "the resume's own job",
    ("app/services/email.py", "select(Job).where(Job.id == job_id)"): "the job being messaged (resumes checked against it)",
    ("app/services/migration.py", "select(Job).where(Job.id == job_id)"): "keyed by the job being migrated",
    ("app/services/tenancy.py", "select(Job.organization_id).where(Job.id == job_id)"): "resolves a job's organization",
    ("app/services/tenancy.py", "select(Job.id).where(Job.organization_id == organization_id)"): "the org predicate itself",
    ("app/worker.py", "select(Job).where(Job.id == item_id)"): "keyed by queue item",
    ("app/worker.py", "select(Job).where(Job.id == job_id)"): "keyed by queue item",
}

_ROOT_SELECT = re.compile(r"select\((Candidate|Job|EmailTemplate|AppSettings|TalentPoolEntry)\b[^\n]*")


def test_static_regression_detector_for_unscoped_root_queries():
    """Flags any new select(<root model>) in services/worker that neither
    carries an organization predicate nor is on the reviewed allow-list.
    Passing this proves nothing by itself - the behavioral tests above do."""
    root = Path(__file__).resolve().parent.parent
    files = sorted((root / "app" / "services").glob("*.py")) + [root / "app" / "worker.py"]
    flagged = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for m in _ROOT_SELECT.finditer(text):
            # The statement: from select( to the end of its enclosing call.
            stmt = text[m.start(): m.start() + 600]
            first_line = m.group(0).strip()
            if "organization_id" in stmt.split("\n\n")[0] or "org_job_ids" in stmt.split("\n\n")[0]:
                continue
            if any(rel == f and first_line.startswith(s) for (f, s) in _STATIC_ALLOWLIST):
                continue
            flagged.append((rel, first_line))
    assert not flagged, "New unscoped root-model queries (scope them or allow-list with a reason):\n" + \
        "\n".join(map(str, flagged))
