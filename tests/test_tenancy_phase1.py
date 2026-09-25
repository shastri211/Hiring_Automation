"""Multi-tenancy Phase 1: roles, forced password change for admin-created
accounts, platform-admin capabilities, per-organization settings, the
talent-pool organization invariant, and org-correct writes.

Real auth dependencies (suite-wide override removed), real test-schema
Postgres, logged-in sessions via real /auth/login. Read-path isolation
(every route/service/background path) is Phase 2 - not covered here.
"""
import asyncio
import secrets
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.api.deps import get_authenticated_user, get_current_user
from app.models.batch import ScreeningBatch
from app.models.candidate import Candidate
from app.models.email import EmailTemplate
from app.models.job import Job
from app.models.organization import Organization
from app.models.profile import CandidateProfile
from app.models.resume import Resume
from app.models.settings import AppSettings
from app.models.talent_pool import TalentPoolEntry
from app.models.user import User
from app.services.auth import hash_password

PASSWORD = "org-password-1"


@pytest.fixture(autouse=True)
def _use_real_auth():
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_authenticated_user, None)
    yield


def _new_client():
    from app.main import app

    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _make_org(db, name=None) -> Organization:
    org = Organization(name=name or f"Org {uuid.uuid4().hex[:6]}")
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


async def _make_user(db, org_id, *, role="admin", platform_admin=False, must_change=False, verified=True) -> User:
    user = User(
        organization_id=org_id,
        email=f"u-{uuid.uuid4().hex[:10]}@tenant.test",
        name="Tenant User",
        hashed_password=hash_password(PASSWORD),
        role=role,
        is_platform_admin=platform_admin,
        must_change_password=must_change,
        email_verified_at=datetime.now(timezone.utc) if verified else None,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _login(client: AsyncClient, user: User, password: str = PASSWORD):
    res = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert res.status_code == 200, res.text
    return res


async def _make_job(db, org_id) -> Job:
    job = Job(organization_id=org_id, title="Role", description="desc", job_profile={"title": "Role"})
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def _make_resume(db, job) -> Resume:
    batch = ScreeningBatch(job_id=job.id, total_resumes=1)
    db.add(batch)
    await db.flush()
    resume = Resume(
        job_id=job.id, batch_id=batch.id, filename="r.pdf", file_hash=secrets.token_hex(16), storage_key="k",
        status="READY",
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


# -- must_change_password: centralized dependency enforcement -------------------

def _dependency_calls(dependant) -> set:
    calls = set()
    for dep in dependant.dependencies:
        if dep.call is not None:
            calls.add(dep.call)
        calls |= _dependency_calls(dep)
    return calls


def _effective_routes():
    """(path, methods, dependant) for every HTTP route, with router-level
    include_router(dependencies=...) folded in. FastAPI 0.141 includes
    routers lazily, so app.router.routes alone doesn't expose them;
    iter_route_contexts flattens them and the effective route carries the
    merged dependency tree."""
    from fastapi.routing import iter_route_contexts
    from app.main import app

    for ctx in iter_route_contexts(app.router.routes):
        effective = getattr(ctx, "_effective_route", None) or ctx.route
        dependant = getattr(effective, "dependant", None)
        if dependant is not None and ctx.methods:
            yield ctx.path, tuple(sorted(ctx.methods)), dependant


def test_only_me_and_change_password_skip_the_password_change_gate():
    """get_authenticated_user without get_current_user = exempt from the
    must_change_password gate. That must be exactly these two routes -
    decided by each route's dependencies, never by URL matching."""
    routes = list(_effective_routes())
    assert len(routes) > 50  # sanity: the walk actually sees the app

    exempt = {
        (path, methods)
        for path, methods, dependant in routes
        if get_authenticated_user in (calls := _dependency_calls(dependant)) and get_current_user not in calls
    }
    assert exempt == {("/auth/me", ("GET",)), ("/auth/change-password", ("POST",))}

    # And the gate really applies router-wide: e.g. GET /jobs/ (auth only via
    # include_router dependencies) resolves get_current_user.
    jobs_list = [d for p, m, d in routes if p == "/jobs/" and m == ("GET",)]
    assert jobs_list and get_current_user in _dependency_calls(jobs_list[0])


# Every other router gets get_current_user as a router-wide default
# (app/main.py's include_router(..., dependencies=_auth_dep)), so a new
# route there is authenticated even if its author forgets a per-route
# Depends. auth.router has no such default - it deliberately mixes public
# routes (signup, login, verify-email) with gated ones declared per-route -
# so nothing else catches a future app/api/auth.py route that forgets its
# own auth dependency. This set is the guardrail: it must be updated
# deliberately (after confirming the new route really is meant to be
# public) whenever a route is added to auth.py, rather than silently
# passing a newly-unauthenticated one.
KNOWN_PUBLIC_AUTH_ROUTES = {
    ("/auth/login", ("POST",)),
    ("/auth/logout", ("POST",)),
    ("/auth/signup", ("POST",)),
    ("/auth/verify-email", ("POST",)),
    ("/auth/resend-verification", ("POST",)),
}


def test_every_auth_router_route_is_authenticated_or_a_known_public_one():
    from app.api.deps import require_admin, require_platform_admin

    auth_dependencies = {get_authenticated_user, get_current_user, require_admin, require_platform_admin}
    auth_routes = [
        (path, methods, dependant) for path, methods, dependant in _effective_routes() if path.startswith("/auth/")
    ]
    assert len(auth_routes) >= 7  # sanity: the walk actually sees auth.py's routes

    unclassified = [
        (path, methods)
        for path, methods, dependant in auth_routes
        if (path, methods) not in KNOWN_PUBLIC_AUTH_ROUTES
        and not (_dependency_calls(dependant) & auth_dependencies)
    ]
    assert not unclassified, (
        f"Route(s) in app/api/auth.py with no auth dependency and not in "
        f"KNOWN_PUBLIC_AUTH_ROUTES: {unclassified}. If a new route is genuinely public, add it to "
        "KNOWN_PUBLIC_AUTH_ROUTES above after confirming that's intentional; otherwise give it an "
        "explicit Depends(get_current_user) (or get_authenticated_user/require_admin/require_platform_admin)."
    )


async def test_admin_created_user_must_change_password_before_anything_else(db_session):
    org = await _make_org(db_session)
    admin = await _make_user(db_session, org.id)
    new_email = f"new-{uuid.uuid4().hex[:8]}@tenant.test"

    async with _new_client() as admin_client:
        await _login(admin_client, admin)
        created = await admin_client.post(
            "/auth/users", json={"email": new_email, "password": "temp-pass-123", "name": "New Member"}
        )
        assert created.status_code == 201
        assert created.json()["role"] == "member"

    async with _new_client() as member:
        login = await member.post("/auth/login", json={"email": new_email, "password": "temp-pass-123"})
        assert login.status_code == 200
        assert login.json()["must_change_password"] is True

        assert (await member.get("/auth/me")).status_code == 200
        blocked = await member.get("/jobs/")
        assert blocked.status_code == 403
        assert blocked.json()["detail"] == {"reason": "password_change_required"}
        assert (await member.get("/settings/")).status_code == 403

        wrong = await member.post(
            "/auth/change-password", json={"current_password": "nope-nope", "new_password": "brand-new-pass"}
        )
        assert wrong.status_code == 400
        weak = await member.post(
            "/auth/change-password", json={"current_password": "temp-pass-123", "new_password": "short"}
        )
        assert weak.status_code == 422
        ok = await member.post(
            "/auth/change-password", json={"current_password": "temp-pass-123", "new_password": "brand-new-pass"}
        )
        assert ok.status_code == 200
        assert (await member.get("/auth/me")).json()["must_change_password"] is False
        assert (await member.get("/jobs/")).status_code == 200

    async with _new_client() as fresh:
        old = await fresh.post("/auth/login", json={"email": new_email, "password": "temp-pass-123"})
        assert old.status_code == 401
        new = await fresh.post("/auth/login", json={"email": new_email, "password": "brand-new-pass"})
        assert new.status_code == 200


async def test_signup_and_cli_style_users_are_never_forced_to_change_password(db_session):
    org = await _make_org(db_session)
    user = await _make_user(db_session, org.id)  # like signup / scripts.create_user
    assert user.must_change_password is False
    async with _new_client() as c:
        await _login(c, user)
        assert (await c.get("/jobs/")).status_code == 200


# -- roles ----------------------------------------------------------------------------

async def test_member_cannot_manage_users_or_settings(db_session):
    org = await _make_org(db_session)
    admin = await _make_user(db_session, org.id)
    member = await _make_user(db_session, org.id, role="member")

    async with _new_client() as c:
        await _login(c, member)
        assert (await c.post(
            "/auth/users", json={"email": "x@y.test", "password": "long-enough", "name": "X"}
        )).status_code == 403
        assert (await c.patch(f"/auth/users/{admin.id}", json={"role": "member"})).status_code == 403
        assert (await c.patch("/settings/", json={"auto_email_on_shortlist": True})).status_code == 403
        # Read access stays.
        assert (await c.get("/settings/")).status_code == 200
        team = await c.get("/auth/users")
        assert team.status_code == 200
        assert {u["id"] for u in team.json()} == {admin.id, member.id}


async def test_user_management_is_scoped_to_the_admins_organization(db_session):
    org_a = await _make_org(db_session)
    org_b = await _make_org(db_session)
    admin_a = await _make_user(db_session, org_a.id)
    user_b = await _make_user(db_session, org_b.id, role="member")

    async with _new_client() as c:
        await _login(c, admin_a)
        res = await c.patch(f"/auth/users/{user_b.id}", json={"is_active": False})
        assert res.status_code == 404
        listed = {u["id"] for u in (await c.get("/auth/users")).json()}
        assert user_b.id not in listed

    await db_session.refresh(user_b)
    assert user_b.is_active is True


async def test_last_active_admin_cannot_be_demoted_or_deactivated(db_session):
    org = await _make_org(db_session)
    admin = await _make_user(db_session, org.id)
    async with _new_client() as c:
        await _login(c, admin)
        for body in ({"role": "member"}, {"is_active": False}):
            res = await c.patch(f"/auth/users/{admin.id}", json=body)
            assert res.status_code == 409
            assert res.json()["detail"]["reason"] == "last_admin"
    await db_session.refresh(admin)
    assert admin.role == "admin" and admin.is_active


async def test_concurrent_demotions_of_the_last_two_admins_leave_one_admin(db_session):
    """Each of the org's two admins demotes the other at the same moment.

    A 2-party barrier holds both requests right before they take the
    organization row lock - i.e. both have already passed require_admin and
    neither has counted admins yet, the exact interleaving that would let
    both succeed and leave zero admins without the lock. The lock then
    serializes them: exactly one succeeds; the other counts after the
    first's commit and is refused (409)."""
    from sqlalchemy.ext.asyncio import AsyncSession

    org = await _make_org(db_session)
    admin_1 = await _make_user(db_session, org.id)
    admin_2 = await _make_user(db_session, org.id)

    barrier = asyncio.Barrier(2)
    original_execute = AsyncSession.execute
    hits = []

    async def _execute_with_barrier(self, statement, *args, **kwargs):
        # Trigger on update_user's organization query itself (lock or not),
        # so the test would also expose the race if the lock were removed.
        sql = str(statement)
        if "FROM organizations" in sql:
            hits.append(1)
            await barrier.wait()
        return await original_execute(self, statement, *args, **kwargs)

    async with _new_client() as c1, _new_client() as c2:
        await _login(c1, admin_1)
        await _login(c2, admin_2)
        with patch.object(AsyncSession, "execute", _execute_with_barrier):
            results = await asyncio.wait_for(
                asyncio.gather(
                    c1.patch(f"/auth/users/{admin_2.id}", json={"role": "member"}),
                    c2.patch(f"/auth/users/{admin_1.id}", json={"role": "member"}),
                ),
                timeout=30,
            )

    assert len(hits) == 2  # both reached the lock point concurrently
    assert sorted(r.status_code for r in results) == [200, 409]
    refused = next(r for r in results if r.status_code == 409)
    assert refused.json()["detail"]["reason"] == "last_admin"
    active_admins = (
        await db_session.execute(
            select(func.count(User.id)).where(
                User.organization_id == org.id, User.role == "admin", User.is_active.is_(True)
            )
        )
    ).scalar_one()
    assert active_admins == 1


# -- platform admin ---------------------------------------------------------------------

async def test_integrations_are_platform_admin_only(db_session):
    org = await _make_org(db_session)
    org_admin = await _make_user(db_session, org.id)
    platform_admin = await _make_user(db_session, org.id, platform_admin=True)

    async with _new_client() as c:
        await _login(c, org_admin)
        assert (await c.get("/integrations/")).status_code == 403
        assert (await c.post("/integrations/smtp/test")).status_code == 403

    with patch("app.api.integrations_status.rate_limit.check", new_callable=AsyncMock, return_value=(True, 1)), \
         patch("app.api.integrations_status._test_smtp", new_callable=AsyncMock, return_value={"ok": True}):
        async with _new_client() as c:
            await _login(c, platform_admin)
            assert (await c.get("/integrations/")).status_code == 200
            assert (await c.post("/integrations/smtp/test")).status_code == 200


async def test_no_api_can_grant_platform_admin(db_session):
    org = await _make_org(db_session)
    admin = await _make_user(db_session, org.id)
    member = await _make_user(db_session, org.id, role="member")
    async with _new_client() as c:
        await _login(c, admin)
        res = await c.patch(f"/auth/users/{member.id}", json={"is_platform_admin": True, "role": "admin"})
        assert res.status_code == 200
    await db_session.refresh(member)
    assert member.role == "admin"
    assert member.is_platform_admin is False


# -- per-organization settings ------------------------------------------------------------

async def test_settings_are_per_organization(db_session):
    org_a = await _make_org(db_session)
    org_b = await _make_org(db_session)
    admin_a = await _make_user(db_session, org_a.id)
    admin_b = await _make_user(db_session, org_b.id)

    async with _new_client() as a, _new_client() as b:
        await _login(a, admin_a)
        await _login(b, admin_b)
        assert (await a.patch("/settings/", json={"min_candidates_to_screen": 3})).status_code == 200
        body_b = (await b.get("/settings/")).json()
        assert body_b["min_candidates_to_screen"] is None
        assert body_b["organization_name"] == org_b.name
        assert (await a.get("/settings/")).json()["id"] != body_b["id"]

    from app.services.settings import settings_service
    assert (await settings_service.get_effective_screening_config(db_session, org_a.id))[0] == 3
    from app.core.config import settings as app_config
    assert (await settings_service.get_effective_screening_config(db_session, org_b.id))[0] == (
        app_config.MIN_CANDIDATES_TO_SCREEN
    )
    rows = (await db_session.execute(
        select(func.count(AppSettings.id)).where(AppSettings.organization_id.in_([org_a.id, org_b.id]))
    )).scalar_one()
    assert rows == 2


async def test_settings_reject_another_organizations_template(db_session):
    org_a = await _make_org(db_session)
    org_b = await _make_org(db_session)
    admin_b = await _make_user(db_session, org_b.id)
    template_a = EmailTemplate(organization_id=org_a.id, name="A only", subject="s", body_content="b")
    db_session.add(template_a)
    await db_session.commit()

    async with _new_client() as b:
        await _login(b, admin_b)
        res = await b.patch("/settings/", json={"shortlist_email_template_id": template_a.id})
        assert res.status_code == 400


# -- org-correct writes ---------------------------------------------------------------------

async def test_writes_carry_the_callers_organization(db_session):
    org = await _make_org(db_session)
    admin = await _make_user(db_session, org.id)

    async with _new_client() as c:
        await _login(c, admin)
        with patch("app.api.jobs._bootstrap_job_profile_and_embedding", new_callable=AsyncMock):
            job_res = await c.post("/jobs/", json={
                "title": "Tenant Job",
                "description": "A sufficiently long and meaningful job description for validation purposes.",
            })
        assert job_res.status_code == 201, job_res.text
        tpl = await c.post("/emails/templates", json={"name": "Welcome", "subject": "Hi", "body_content": "Body"})
        assert tpl.status_code == 201

    job = (await db_session.execute(select(Job).where(Job.id == job_res.json()["id"]))).scalar_one()
    assert job.organization_id == org.id
    template = (await db_session.execute(select(EmailTemplate).where(EmailTemplate.id == tpl.json()["id"]))).scalar_one()
    assert template.organization_id == org.id


async def test_template_names_are_unique_per_organization_only(db_session):
    org_a = await _make_org(db_session)
    org_b = await _make_org(db_session)
    admin_a = await _make_user(db_session, org_a.id)
    admin_b = await _make_user(db_session, org_b.id)
    body = {"name": "Shared Name", "subject": "s", "body_content": "b"}
    async with _new_client() as a, _new_client() as b:
        await _login(a, admin_a)
        await _login(b, admin_b)
        assert (await a.post("/emails/templates", json=body)).status_code == 201
        assert (await b.post("/emails/templates", json=body)).status_code == 201
        assert (await a.post("/emails/templates", json=body)).status_code == 400


async def test_candidate_identity_is_created_and_matched_within_the_jobs_organization(db_session):
    from app.services import candidate_identity

    org_a = await _make_org(db_session)
    org_b = await _make_org(db_session)
    email = f"cand-{uuid.uuid4().hex[:8]}@example.com"

    job_a = await _make_job(db_session, org_a.id)
    job_b = await _make_job(db_session, org_b.id)
    resume_a = await _make_resume(db_session, job_a)
    resume_b = await _make_resume(db_session, job_b)
    resume_a2 = await _make_resume(db_session, job_a)

    profile = CandidateProfile(resume_id=resume_a.id, name="Cand", email=email)
    cand_a = await candidate_identity.resolve_candidate_for_resume(
        db_session, resume_a, profile, organization_id=org_a.id
    )
    cand_b = await candidate_identity.resolve_candidate_for_resume(
        db_session, resume_b, CandidateProfile(resume_id=resume_b.id, name="Cand", email=email),
        organization_id=org_b.id,
    )
    cand_a2 = await candidate_identity.resolve_candidate_for_resume(
        db_session, resume_a2, CandidateProfile(resume_id=resume_a2.id, name="Cand", email=email),
        organization_id=org_a.id,
    )
    await db_session.commit()

    assert cand_a != cand_b  # same email, different organizations -> separate people
    assert cand_a2 == cand_a  # same organization -> matched
    orgs = dict((await db_session.execute(
        select(Candidate.id, Candidate.organization_id).where(Candidate.id.in_([cand_a, cand_b]))
    )).all())
    assert orgs == {cand_a: org_a.id, cand_b: org_b.id}


# -- talent-pool organization invariant ---------------------------------------------------------

async def test_talent_pool_rejects_another_organizations_resume(db_session):
    org_a = await _make_org(db_session)
    org_b = await _make_org(db_session)
    admin_b = await _make_user(db_session, org_b.id)
    resume_a = await _make_resume(db_session, await _make_job(db_session, org_a.id))

    async with _new_client() as b:
        await _login(b, admin_b)
        res = await b.post("/talent-pool/", json={"resume_id": resume_a.id})
        assert res.status_code == 404
    assert (await db_session.execute(
        select(func.count(TalentPoolEntry.id)).where(TalentPoolEntry.resume_id == resume_a.id)
    )).scalar_one() == 0


async def test_talent_pool_added_from_job_never_crosses_organizations(db_session):
    org_a = await _make_org(db_session)
    org_b = await _make_org(db_session)
    admin_b = await _make_user(db_session, org_b.id)
    job_a = await _make_job(db_session, org_a.id)
    job_b = await _make_job(db_session, org_b.id)
    resume_b = await _make_resume(db_session, job_b)

    async with _new_client() as b:
        await _login(b, admin_b)
        with patch("app.api.talent_pool.get_candidate_summaries", new_callable=AsyncMock, return_value={}):
            res = await b.post("/talent-pool/", json={"resume_id": resume_b.id, "added_from_job_id": job_a.id})
        assert res.status_code == 201
        assert res.json()["added_from_job_id"] == job_b.id

    await _assert_talent_pool_invariant(db_session)


async def _assert_talent_pool_invariant(db):
    """For every entry: its own organization == its resume's job's
    organization == its added_from_job's organization."""
    from sqlalchemy.orm import aliased

    ResumeJob = aliased(Job)
    FromJob = aliased(Job)
    rows = (await db.execute(
        select(TalentPoolEntry.id, TalentPoolEntry.organization_id, ResumeJob.organization_id, FromJob.organization_id)
        .join(Resume, Resume.id == TalentPoolEntry.resume_id)
        .join(ResumeJob, ResumeJob.id == Resume.job_id)
        .outerjoin(FromJob, FromJob.id == TalentPoolEntry.added_from_job_id)
    )).all()
    assert rows
    for entry_id, entry_org, resume_org, from_org in rows:
        assert entry_org == resume_org, entry_id
        assert from_org in (None, entry_org), entry_id
