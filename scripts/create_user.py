"""Bootstrap the first HR user account.

There is no public signup by design (this is an internal tool) - every
account after the first is created in-app via a logged-in HR user calling
POST /auth/users. This script exists solely to solve the bootstrap problem:
how does the very first account get created.

Run once, from the repo root, with the app's normal environment/venv active:

    python -m scripts.create_user

Prompts for email/name/password interactively (password via getpass, so it
never touches shell history or process listings) and inserts the User row
directly through the app's async session.
"""
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.services.auth import hash_password


async def create_user(email: str, name: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            print(f"A user with email {email!r} already exists.", file=sys.stderr)
            sys.exit(1)

        user = User(email=email, name=name, hashed_password=hash_password(password))
        db.add(user)
        await db.commit()
        await db.refresh(user)
        print(f"Created user id={user.id} email={user.email!r} name={user.name!r}")


def main() -> None:
    email = input("Email: ").strip()
    if not email:
        print("Email is required.", file=sys.stderr)
        sys.exit(1)

    name = input("Name: ").strip()
    if not name:
        print("Name is required.", file=sys.stderr)
        sys.exit(1)

    password = getpass.getpass("Password: ")
    if not password:
        print("Password is required.", file=sys.stderr)
        sys.exit(1)

    password_confirm = getpass.getpass("Confirm password: ")
    if password != password_confirm:
        print("Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(create_user(email, name, password))


if __name__ == "__main__":
    main()
