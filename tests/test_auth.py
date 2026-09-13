"""Tests for the real login/session flow (app/api/auth.py, app/api/deps.py).

Unlike the rest of the suite, these tests must NOT run against the
autouse get_current_user override installed in tests/conftest.py (that
override exists purely so the other 267+ pre-existing tests don't need to
know about auth). The `_use_real_auth` fixture below pops that override for
every test in this module so we're actually exercising the real dependency.
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.deps import get_current_user
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services.auth import hash_password

_GENERIC_LOGIN_ERROR = "Incorrect email or password"


@pytest.fixture(autouse=True)
def _use_real_auth():
    """Pop the global test-suite override so get_current_user runs for real."""
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)
    yield
    # The conftest.py autouse fixture re-installs the override on its own
    # teardown for the next test; nothing else to restore here.


@pytest.fixture
async def real_user(db_session):
    """A real, committed User row with a known plaintext password."""
    email = f"auth-test-{uuid.uuid4().hex}@example.com"
    password = "correct-horse-battery-staple"
    user = User(email=email, name="Auth Test User", hashed_password=hash_password(password))
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    try:
        yield user, password
    finally:
        await db_session.delete(user)
        await db_session.commit()


@pytest.mark.asyncio
async def test_login_success_sets_cookie_and_returns_user(client: AsyncClient, real_user):
    user, password = real_user

    response = await client.post("/auth/login", json={"email": user.email, "password": password})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user.id
    assert body["email"] == user.email
    assert body["name"] == user.name
    assert "hashed_password" not in body
    assert "password" not in body
    assert "access_token" in response.cookies


@pytest.mark.asyncio
async def test_login_wrong_password_is_401_with_generic_message(client: AsyncClient, real_user):
    user, _ = real_user

    response = await client.post("/auth/login", json={"email": user.email, "password": "definitely-wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == _GENERIC_LOGIN_ERROR


@pytest.mark.asyncio
async def test_login_unknown_email_is_401_with_same_generic_message(client: AsyncClient):
    response = await client.post(
        "/auth/login", json={"email": f"nobody-{uuid.uuid4().hex}@example.com", "password": "whatever"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == _GENERIC_LOGIN_ERROR


@pytest.mark.asyncio
async def test_me_without_cookie_is_401(client: AsyncClient):
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_valid_cookie_returns_the_logged_in_user(client: AsyncClient, real_user):
    user, password = real_user

    login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert login_response.status_code == 200

    me_response = await client.get("/auth/me")
    assert me_response.status_code == 200
    body = me_response.json()
    assert body["id"] == user.id
    assert body["email"] == user.email


@pytest.mark.asyncio
async def test_logout_clears_session(client: AsyncClient, real_user):
    user, password = real_user

    login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert login_response.status_code == 200
    assert (await client.get("/auth/me")).status_code == 200

    logout_response = await client.post("/auth/logout")
    assert logout_response.status_code == 200

    assert (await client.get("/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_users_endpoints_require_auth(client: AsyncClient):
    assert (await client.get("/auth/users")).status_code == 401
    assert (
        await client.post(
            "/auth/users", json={"email": "nobody@example.com", "password": "x", "name": "Nobody"}
        )
    ).status_code == 401


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_email(client: AsyncClient, real_user):
    user, password = real_user
    login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert login_response.status_code == 200

    response = await client.post(
        "/auth/users", json={"email": user.email, "password": "another-password", "name": "Duplicate"}
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_and_list_users(client: AsyncClient, real_user):
    user, password = real_user
    login_response = await client.post("/auth/login", json={"email": user.email, "password": password})
    assert login_response.status_code == 200

    new_email = f"auth-test-{uuid.uuid4().hex}@example.com"
    try:
        create_response = await client.post(
            "/auth/users", json={"email": new_email, "password": "s3cret-password", "name": "New Teammate"}
        )
        assert create_response.status_code == 201
        created_body = create_response.json()
        assert created_body["email"] == new_email
        assert "hashed_password" not in created_body

        list_response = await client.get("/auth/users")
        assert list_response.status_code == 200
        emails = [u["email"] for u in list_response.json()]
        assert new_email in emails
    finally:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.email == new_email))
            created = result.scalar_one_or_none()
            if created is not None:
                await session.delete(created)
                await session.commit()


@pytest.mark.asyncio
async def test_existing_protected_route_401s_without_session(client: AsyncClient):
    """A pre-existing endpoint (GET /jobs/) must require auth once the
    global test override is removed - proving the router-level
    dependencies=[Depends(get_current_user)] wiring in app/main.py works."""
    response = await client.get("/jobs/")
    assert response.status_code == 401
