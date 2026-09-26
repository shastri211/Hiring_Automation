"""Failed-login lockout, forgot/reset password, and password-bound sessions
(app/api/auth.py, app/services/auth.py, app/api/deps.py).

Runs against the real auth dependencies, the test-schema Postgres, an
in-memory rate limiter and a mocked email provider - no SMTP or Redis.
"""
import re
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.deps import get_authenticated_user, get_current_user
from app.core.config import settings
from app.models.user import User
from app.services import rate_limit
from app.services.auth import create_access_token, create_verification_token, hash_password
from tenancy_fixtures import TEST_ORG_ID

PASSWORD = "correct-horse-battery"


@pytest.fixture(autouse=True)
def _use_real_auth():
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_authenticated_user, None)
    yield


class _FakeLimiter:
    def __init__(self):
        self.counts = {}

    async def check(self, key, limit, window_seconds):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key] <= limit, 99

    async def peek(self, key, window_seconds):
        return self.counts.get(key, 0), 99

    async def hit(self, key, window_seconds):
        self.counts[key] = self.counts.get(key, 0) + 1

    async def clear(self, key, window_seconds):
        self.counts.pop(key, None)


@pytest.fixture
def limiter():
    fake = _FakeLimiter()
    with patch.object(rate_limit, "check", side_effect=fake.check), \
         patch.object(rate_limit, "peek", side_effect=fake.peek), \
         patch.object(rate_limit, "hit", side_effect=fake.hit), \
         patch.object(rate_limit, "clear", side_effect=fake.clear):
        yield fake


@pytest.fixture
def mock_send():
    with patch("app.api.auth.email_service.provider.send_email", new_callable=AsyncMock) as m:
        yield m


@pytest.fixture(autouse=True)
def _public_base_url():
    with patch("app.core.config.settings.PUBLIC_APP_BASE_URL", "https://app.example.com"):
        yield


async def _make_user(db_session, *, verified=True, must_change_password=False) -> User:
    user = User(
        organization_id=TEST_ORG_ID,
        email=f"pw-{uuid.uuid4().hex[:10]}@acme.test",
        name="Pat",
        hashed_password=hash_password(PASSWORD),
        role="admin",
        email_verified_at=datetime.now(timezone.utc) if verified else None,
        must_change_password=must_change_password,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _login(client, email, password):
    return await client.post("/auth/login", json={"email": email, "password": password})


def _reset_token_from(mock_send) -> str:
    body = mock_send.await_args.args[2]
    return re.search(r"/reset-password\?token=(\S+)", body).group(1)


# -- failed-login lockout ----------------------------------------------------------

async def test_email_is_locked_after_max_failures_even_with_right_password(client: AsyncClient, db_session, limiter):
    user = await _make_user(db_session)
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_EMAIL):
        assert (await _login(client, user.email, "wrong-password")).status_code == 401

    res = await _login(client, user.email, PASSWORD)
    assert res.status_code == 429
    assert res.json()["detail"]["reason"] == "too_many_login_attempts"
    assert "Try again in" in res.json()["detail"]["message"]
    assert res.headers["Retry-After"] == "99"


async def test_unknown_emails_are_locked_out_the_same_way(client: AsyncClient, limiter):
    email = f"nobody-{uuid.uuid4().hex}@acme.test"
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_EMAIL):
        assert (await _login(client, email, "whatever-pw")).status_code == 401
    assert (await _login(client, email, "whatever-pw")).status_code == 429


async def test_success_clears_the_email_failure_count(client: AsyncClient, db_session, limiter):
    user = await _make_user(db_session)
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_EMAIL - 1):
        await _login(client, user.email, "wrong-password")
    assert (await _login(client, user.email, PASSWORD)).status_code == 200
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_EMAIL - 1):
        assert (await _login(client, user.email, "wrong-password")).status_code == 401
    assert (await _login(client, user.email, PASSWORD)).status_code == 200


async def test_ip_is_locked_after_failures_across_many_emails(client: AsyncClient, db_session, limiter):
    user = await _make_user(db_session)
    with patch("app.core.config.settings.LOGIN_MAX_FAILURES_PER_IP", 3):
        for _ in range(3):
            await _login(client, f"x-{uuid.uuid4().hex}@acme.test", "wrong-password")
        assert (await _login(client, user.email, PASSWORD)).status_code == 429


async def test_login_still_works_when_the_limiter_is_unavailable(client: AsyncClient, db_session):
    user = await _make_user(db_session)
    down = AsyncMock(side_effect=rate_limit.RateLimiterUnavailable("redis down"))
    with patch.object(rate_limit, "peek", down), patch.object(rate_limit, "hit", down), \
         patch.object(rate_limit, "clear", down):
        assert (await _login(client, user.email, "wrong-password")).status_code == 401
        assert (await _login(client, user.email, PASSWORD)).status_code == 200


# -- forgot / reset password -------------------------------------------------------

async def test_forgot_password_emails_a_reset_link_only_to_verified_accounts(client: AsyncClient, db_session, limiter, mock_send):
    verified = await _make_user(db_session)
    unverified = await _make_user(db_session, verified=False)

    for email in (verified.email, unverified.email, f"nobody-{uuid.uuid4().hex}@acme.test"):
        res = await client.post("/auth/forgot-password", json={"email": email.upper()})
        assert res.status_code == 202
        assert res.json() == {"status": "check_inbox"}

    mock_send.assert_awaited_once()
    assert mock_send.await_args.args[0] == verified.email
    assert "https://app.example.com/reset-password?token=" in mock_send.await_args.args[2]


async def test_forgot_password_is_rate_limited_per_email(client: AsyncClient, db_session, limiter, mock_send):
    user = await _make_user(db_session)
    for _ in range(settings.FORGOT_PASSWORD_MAX_PER_EMAIL_PER_HOUR):
        assert (await client.post("/auth/forgot-password", json={"email": user.email})).status_code == 202
    assert (await client.post("/auth/forgot-password", json={"email": user.email})).status_code == 429


async def test_reset_password_sets_new_password_and_link_works_once(client: AsyncClient, db_session, limiter, mock_send):
    user = await _make_user(db_session, must_change_password=True)
    await client.post("/auth/forgot-password", json={"email": user.email})
    token = _reset_token_from(mock_send)

    res = await client.post("/auth/reset-password", json={"token": token, "new_password": "brand-new-pass"})
    assert res.status_code == 200
    assert res.json() == {"status": "password_reset"}

    assert (await _login(client, user.email, PASSWORD)).status_code == 401
    assert (await _login(client, user.email, "brand-new-pass")).status_code == 200
    refreshed = (await db_session.execute(
        select(User).where(User.id == user.id).execution_options(populate_existing=True)
    )).scalar_one()
    assert refreshed.must_change_password is False

    again = await client.post("/auth/reset-password", json={"token": token, "new_password": "another-pass-1"})
    assert again.status_code == 400
    assert again.json()["detail"] == {"reason": "invalid_or_expired_token"}


async def test_reset_password_rejects_other_token_kinds_and_weak_passwords(client: AsyncClient, db_session, limiter, mock_send):
    user = await _make_user(db_session)
    for wrong in (create_access_token(user.id, user.hashed_password), create_verification_token(user.id), "garbage"):
        res = await client.post("/auth/reset-password", json={"token": wrong, "new_password": "brand-new-pass"})
        assert res.status_code == 400

    await client.post("/auth/forgot-password", json={"email": user.email})
    token = _reset_token_from(mock_send)
    weak = await client.post("/auth/reset-password", json={"token": token, "new_password": "short"})
    assert weak.status_code == 422
    # A rejected attempt doesn't consume the link.
    ok = await client.post("/auth/reset-password", json={"token": token, "new_password": "brand-new-pass"})
    assert ok.status_code == 200


# -- password-bound sessions -------------------------------------------------------

async def test_reset_password_logs_out_existing_sessions(client: AsyncClient, db_session, limiter, mock_send):
    user = await _make_user(db_session)
    assert (await _login(client, user.email, PASSWORD)).status_code == 200
    old_session = client.cookies.get("access_token")

    await client.post("/auth/forgot-password", json={"email": user.email})
    token = _reset_token_from(mock_send)
    assert (await client.post("/auth/reset-password", json={"token": token, "new_password": "brand-new-pass"})).status_code == 200

    client.cookies.set("access_token", old_session)
    assert (await client.get("/auth/me")).status_code == 401


async def test_change_password_keeps_this_session_and_ends_others(client: AsyncClient, db_session, limiter):
    user = await _make_user(db_session)
    assert (await _login(client, user.email, PASSWORD)).status_code == 200
    other_session = client.cookies.get("access_token")

    res = await client.post(
        "/auth/change-password", json={"current_password": PASSWORD, "new_password": "brand-new-pass"}
    )
    assert res.status_code == 200
    assert (await client.get("/auth/me")).status_code == 200  # re-issued cookie

    client.cookies.set("access_token", other_session)
    assert (await client.get("/auth/me")).status_code == 401


async def test_session_without_password_binding_is_rejected(client: AsyncClient, db_session):
    """Tokens issued before sessions were bound to the password carry no
    fingerprint claim and must not authenticate."""
    from datetime import timedelta
    from app.services import auth as auth_service

    user = await _make_user(db_session)
    legacy = auth_service._encode(user.id, auth_service.SESSION_PURPOSE, timedelta(hours=1))
    client.cookies.set("access_token", legacy)
    assert (await client.get("/auth/me")).status_code == 401
