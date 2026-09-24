"""Self-service company signup, email verification, token-purpose isolation
and email normalization (app/api/auth.py, app/services/auth.py).

Runs against the real auth dependencies (the suite-wide override is
removed), the real test-schema Postgres, a fake in-memory rate limiter, and
a mocked email provider - no SMTP or Redis.
"""
import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.api.deps import get_authenticated_user, get_current_user
from app.models.organization import Organization
from app.models.settings import AppSettings
from app.models.user import User
from app.services import auth as auth_service
from app.services import rate_limit
from app.services.auth import create_access_token, create_verification_token, hash_password

CHECK_INBOX = {"status": "check_inbox"}


@pytest.fixture(autouse=True)
def _use_real_auth():
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_authenticated_user, None)
    yield


class _FakeLimiter:
    def __init__(self):
        self.counts = {}
        self.keys = []

    async def check(self, key, limit, window_seconds):
        self.keys.append(key)
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key] <= limit, 99


@pytest.fixture
def limiter():
    fake = _FakeLimiter()
    with patch.object(rate_limit, "check", side_effect=fake.check):
        yield fake


@pytest.fixture
def mock_send():
    with patch("app.api.auth.email_service.provider.send_email", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture(autouse=True)
def _public_base_url():
    with patch("app.core.config.settings.PUBLIC_APP_BASE_URL", "https://app.example.com"):
        yield


def _email():
    return f"owner-{uuid.uuid4().hex[:10]}@acme.test"


def _signup_body(email, **overrides):
    body = {"company_name": "Acme Corp", "name": "Olive Owner", "email": email, "password": "sup3r-secret"}
    body.update(overrides)
    return body


async def _count(db, model, *where):
    return (await db.execute(select(func.count()).select_from(model).where(*where))).scalar_one()


async def _user(db, email):
    return (
        await db.execute(select(User).where(User.email == email).execution_options(populate_existing=True))
    ).scalar_one_or_none()


def _token_from_email(mock_send) -> str:
    body = mock_send.await_args.args[2]
    match = re.search(r"/verify-email\?token=(\S+)", body)
    assert match, body
    return match.group(1)


# -- signup ----------------------------------------------------------------------

async def test_signup_creates_org_admin_and_settings_atomically(client: AsyncClient, db_session, limiter, mock_send):
    email = _email()
    res = await client.post("/auth/signup", json=_signup_body(email))
    assert res.status_code == 202
    assert res.json() == CHECK_INBOX

    user = await _user(db_session, email)
    assert user is not None
    assert user.role == "admin"
    assert user.email_verified_at is None
    assert user.must_change_password is False
    assert user.is_platform_admin is False
    org = (await db_session.execute(select(Organization).where(Organization.id == user.organization_id))).scalar_one()
    assert org.name == "Acme Corp"
    assert await _count(db_session, AppSettings, AppSettings.organization_id == org.id) == 1

    mock_send.assert_awaited_once()
    assert mock_send.await_args.args[0] == email
    token = _token_from_email(mock_send)
    assert auth_service.decode_verification_token(token) == user.id


@pytest.mark.parametrize("verified", [True, False])
async def test_signup_with_existing_email_is_a_generic_noop(client, db_session, limiter, mock_send, verified):
    email = _email()
    assert (await client.post("/auth/signup", json=_signup_body(email))).status_code == 202
    user = await _user(db_session, email)
    if verified:
        user.email_verified_at = datetime.now(timezone.utc)
        await db_session.commit()
    orgs_before = await _count(db_session, Organization)
    users_before = await _count(db_session, User)
    mock_send.reset_mock()

    # Also a case/whitespace variant of the same address.
    res = await client.post(
        "/auth/signup", json=_signup_body(f"  {email.upper()} ", company_name="Other Co", password="another-pass")
    )
    assert res.status_code == 202
    assert res.json() == CHECK_INBOX
    assert await _count(db_session, Organization) == orgs_before
    assert await _count(db_session, User) == users_before
    mock_send.assert_not_awaited()


async def test_concurrent_signups_same_email_create_one_account(client, db_session, limiter, mock_send):
    email = _email()
    results = await asyncio.gather(
        client.post("/auth/signup", json=_signup_body(email, company_name="Race A")),
        client.post("/auth/signup", json=_signup_body(email, company_name="Race B")),
    )
    assert [r.status_code for r in results] == [202, 202]
    assert all(r.json() == CHECK_INBOX for r in results)
    assert await _count(db_session, User, User.email == email) == 1
    assert await _count(db_session, Organization, Organization.name.in_(["Race A", "Race B"])) == 1


async def test_signup_smtp_failure_keeps_account_and_resend_recovers(client, db_session, limiter, mock_send):
    email = _email()
    mock_send.side_effect = Exception("SMTP down")
    res = await client.post("/auth/signup", json=_signup_body(email))
    assert res.status_code == 202
    assert res.json() == CHECK_INBOX
    user = await _user(db_session, email)
    assert user is not None and user.email_verified_at is None

    mock_send.side_effect = None
    mock_send.reset_mock()
    res = await client.post("/auth/resend-verification", json={"email": email})
    assert res.status_code == 202
    token = _token_from_email(mock_send)
    assert (await client.post("/auth/verify-email", json={"token": token})).status_code == 200
    assert (await _user(db_session, email)).email_verified_at is not None


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"password": "short"}, "weak_password"),
        ({"email": "not-an-email"}, "invalid_email"),
        ({"company_name": "   "}, "invalid_company_name"),
        ({"name": ""}, "invalid_name"),
    ],
)
async def test_signup_validation(client, db_session, limiter, mock_send, overrides, reason):
    res = await client.post("/auth/signup", json={**_signup_body(_email()), **overrides})
    assert res.status_code == 422
    assert res.json()["detail"]["reason"] == reason
    mock_send.assert_not_awaited()


async def test_signup_is_rate_limited_per_ip(client, db_session, limiter, mock_send):
    with patch("app.core.config.settings.SIGNUP_MAX_PER_IP_PER_HOUR", 1):
        assert (await client.post("/auth/signup", json=_signup_body(_email()))).status_code == 202
        res = await client.post("/auth/signup", json=_signup_body(_email()))
    assert res.status_code == 429
    assert res.headers["Retry-After"] == "99"
    assert all(k.startswith("signup:ip:") for k in limiter.keys)


# -- verification --------------------------------------------------------------

async def _signed_up_user(client, db_session, mock_send, email=None, password="sup3r-secret"):
    email = email or _email()
    assert (await client.post("/auth/signup", json=_signup_body(email, password=password))).status_code == 202
    return await _user(db_session, email), password


async def test_login_blocked_until_verified_and_reason_only_after_correct_password(
    client, db_session, limiter, mock_send
):
    user, password = await _signed_up_user(client, db_session, mock_send)

    wrong = await client.post("/auth/login", json={"email": user.email, "password": "wrong-password"})
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == "Incorrect email or password"

    unverified = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert unverified.status_code == 403
    assert unverified.json()["detail"] == {"reason": "email_not_verified"}
    assert "access_token" not in unverified.cookies

    token = _token_from_email(mock_send)
    assert (await client.post("/auth/verify-email", json={"token": token})).json() == {"status": "verified"}
    # Idempotent.
    assert (await client.post("/auth/verify-email", json={"token": token})).status_code == 200

    ok = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert ok.status_code == 200
    body = ok.json()
    assert body["role"] == "admin"
    assert body["organization"]["name"] == "Acme Corp"
    assert body["is_platform_admin"] is False
    assert (await client.get("/auth/me")).status_code == 200


async def test_verify_rejects_expired_tampered_and_wrong_purpose_tokens(client, db_session, limiter, mock_send):
    user, _ = await _signed_up_user(client, db_session, mock_send)

    expired = auth_service._encode(user.id, auth_service.VERIFY_EMAIL_PURPOSE, timedelta(seconds=-5))
    valid = create_verification_token(user.id)
    tampered = valid[:-3] + ("AAA" if not valid.endswith("AAA") else "BBB")
    session_token = create_access_token(user.id)
    no_purpose = auth_service.jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        auth_service.settings.SECRET_KEY,
        algorithm=auth_service.JWT_ALGORITHM,
    )

    for token in (expired, tampered, session_token, no_purpose, "garbage"):
        res = await client.post("/auth/verify-email", json={"token": token})
        assert res.status_code == 400, token
        assert res.json()["detail"] == {"reason": "invalid_or_expired_token"}
    assert (await _user(db_session, user.email)).email_verified_at is None


# -- token purpose isolation -----------------------------------------------------

async def test_verification_token_is_not_a_session(client, db_session, limiter, mock_send):
    user, _ = await _signed_up_user(client, db_session, mock_send)
    user.email_verified_at = datetime.now(timezone.utc)  # even a verified user
    await db_session.commit()

    client.cookies.set("access_token", create_verification_token(user.id))
    assert (await client.get("/auth/me")).status_code == 401
    assert (await client.get("/jobs/")).status_code == 401

    no_purpose = auth_service.jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        auth_service.settings.SECRET_KEY,
        algorithm=auth_service.JWT_ALGORITHM,
    )
    client.cookies.set("access_token", no_purpose)
    assert (await client.get("/auth/me")).status_code == 401

    client.cookies.set("access_token", create_access_token(user.id))
    assert (await client.get("/auth/me")).status_code == 200


async def test_session_token_cannot_verify_email(client, db_session, limiter, mock_send):
    user, _ = await _signed_up_user(client, db_session, mock_send)
    res = await client.post("/auth/verify-email", json={"token": create_access_token(user.id)})
    assert res.status_code == 400
    assert (await _user(db_session, user.email)).email_verified_at is None


# -- resend ------------------------------------------------------------------------

async def test_resend_is_generic_and_only_sends_for_unverified(client, db_session, limiter, mock_send):
    user, _ = await _signed_up_user(client, db_session, mock_send)
    mock_send.reset_mock()

    unknown = await client.post("/auth/resend-verification", json={"email": _email()})
    assert unknown.status_code == 202 and unknown.json() == CHECK_INBOX
    mock_send.assert_not_awaited()

    res = await client.post("/auth/resend-verification", json={"email": f" {user.email.upper()} "})
    assert res.status_code == 202 and res.json() == CHECK_INBOX
    mock_send.assert_awaited_once()

    user.email_verified_at = datetime.now(timezone.utc)
    await db_session.commit()
    mock_send.reset_mock()
    res = await client.post("/auth/resend-verification", json={"email": user.email})
    assert res.status_code == 202 and res.json() == CHECK_INBOX
    mock_send.assert_not_awaited()


async def test_resend_rate_limit_keys_hash_the_email(client, db_session, limiter, mock_send):
    email = _email()
    with patch("app.core.config.settings.VERIFY_RESEND_MAX_PER_EMAIL_PER_HOUR", 1):
        assert (await client.post("/auth/resend-verification", json={"email": email})).status_code == 202
        res = await client.post("/auth/resend-verification", json={"email": email})
    assert res.status_code == 429

    email_keys = [k for k in limiter.keys if k.startswith("resend:email:")]
    assert email_keys
    assert all(re.fullmatch(r"resend:email:[0-9a-f]{16}", k) for k in email_keys)
    assert any(k.startswith("resend:ip:") for k in limiter.keys)
    local = email.split("@")[0]
    for key in limiter.keys:
        assert email not in key and local not in key and "acme.test" not in key


# -- normalization -----------------------------------------------------------------

async def test_emails_are_normalized_everywhere(client, db_session, limiter, mock_send):
    raw = f"  Ada.{uuid.uuid4().hex[:6]}@Example.COM "
    normalized = raw.strip().lower()
    assert (await client.post("/auth/signup", json=_signup_body(raw, password="ada-password"))).status_code == 202
    user = await _user(db_session, normalized)
    assert user is not None and user.email == normalized

    user.email_verified_at = datetime.now(timezone.utc)
    await db_session.commit()
    res = await client.post("/auth/login", json={"email": raw.upper(), "password": "ada-password"})
    assert res.status_code == 200
    assert res.json()["email"] == normalized

    # Invite with a case variant of an existing address is rejected.
    dup = await client.post(
        "/auth/users", json={"email": normalized.upper(), "password": "temp-password", "name": "Dup"}
    )
    assert dup.status_code == 400


async def test_users_email_lower_unique_index_blocks_case_duplicates(db_session):
    """Second guard behind normalization: even a raw insert of a case
    variant is rejected by the DB."""
    from sqlalchemy.exc import IntegrityError
    from tenancy_fixtures import TEST_ORG_ID

    email = _email()
    db_session.add(User(organization_id=TEST_ORG_ID, email=email, name="A", hashed_password=hash_password("x" * 8)))
    await db_session.commit()
    db_session.add(User(organization_id=TEST_ORG_ID, email=email.upper(), name="B", hashed_password=hash_password("x" * 8)))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
