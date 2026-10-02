"""Create an HR user from the command line (server access required).

Normal onboarding happens in-app: a company signs up at /signup (becoming
its first admin), and admins add teammates from Settings. This script
covers bootstrap/operator cases: creating a user in an existing or new
organization, and - the only way it can be granted - platform-admin
(shared provider configuration; see app/api/integrations_status.py).

Run from the repo root, with the app's normal environment/venv active:

    python -m scripts.create_user                   # org admin
    python -m scripts.create_user --platform-admin  # also a platform admin

Prompts for organization, email, name and password interactively (password
via getpass, so it never touches shell history or process listings). The
created user is an admin of the chosen organization, already verified, and
not forced to change the password (they chose it themselves).
"""
import argparse
import asyncio
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import getpass
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.organization import Organization
from app.models.settings import AppSettings
from app.models.user import User
from app.services.auth import MIN_PASSWORD_LENGTH, hash_password, normalize_user_email


async def _list_organizations() -> list[Organization]:
    async with AsyncSessionLocal() as db:
        return list((await db.execute(select(Organization).order_by(Organization.id))).scalars().all())


async def create_user(
    *, email: str, name: str, password: str, organization_id: int | None, new_org_name: str | None,
    platform_admin: bool,
) -> None:
    email = normalize_user_email(email)
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            print(f"A user with email {email!r} already exists.", file=sys.stderr)
            sys.exit(1)

        if organization_id is None:
            org = Organization(name=new_org_name)
            db.add(org)
            await db.flush()
            db.add(AppSettings(organization_id=org.id))
            organization_id = org.id

        user = User(
            organization_id=organization_id,
            email=email,
            name=name,
            hashed_password=hash_password(password),
            role="admin",
            email_verified_at=datetime.now(timezone.utc),
            must_change_password=False,
            is_platform_admin=platform_admin,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(
            f"Created user id={user.id} email={user.email!r} name={user.name!r} "
            f"organization_id={organization_id} role=admin platform_admin={platform_admin}"
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--platform-admin", action="store_true",
        help="Also grant platform-admin (shared provider configuration). Not grantable via any API.",
    )
    args = parser.parse_args()

    orgs = await _list_organizations()
    organization_id: int | None = None
    new_org_name: str | None = None
    if orgs:
        print("Organizations:")
        for org in orgs:
            print(f"  {org.id}: {org.name}")
    choice = input("Organization id (blank = create a new organization): ").strip()
    if choice:
        if not choice.isdigit() or int(choice) not in {o.id for o in orgs}:
            print("Unknown organization id.", file=sys.stderr)
            sys.exit(1)
        organization_id = int(choice)
    else:
        new_org_name = input("New organization name: ").strip()
        if not new_org_name:
            print("Organization name is required.", file=sys.stderr)
            sys.exit(1)

    email = normalize_user_email(input("Email: "))
    if not email:
        print("Email is required.", file=sys.stderr)
        sys.exit(1)

    name = input("Name: ").strip()
    if not name:
        print("Name is required.", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("Password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", file=sys.stderr)
        sys.exit(1)

    password_confirm = getpass.getpass("Confirm password: ")
    if password != password_confirm:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    await create_user(
        email=email, name=name, password=password, organization_id=organization_id,
        new_org_name=new_org_name, platform_admin=args.platform_admin,
    )


if __name__ == "__main__":
    asyncio.run(main())
