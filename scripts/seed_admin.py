"""Seed initial default roles and a super admin user in the database.

Usage:
    python scripts/seed_admin.py --email admin@example.com --password AdminPassword123! --name "Super Admin"
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import uuid

from sqlalchemy import select

from app.core.auth.hashing import hash_password
from app.core.security.admin_permissions import DEFAULT_ROLE_PERMISSIONS
from app.persistence.sqlalchemy.connection import async_session_factory
from app.persistence.sqlalchemy.models.admin import Admin, AdminRole
from app.persistence.sqlalchemy.models.users import User


DEFAULT_ROLES_META = [
    {
        "slug": "super_admin",
        "name": "Super Administrator",
        "description": "Full access to all platform operations and administrative actions.",
        "permissions": list(DEFAULT_ROLE_PERMISSIONS["super_admin"]),
        "is_system": True,
    },
    {
        "slug": "operations_admin",
        "name": "Operations Administrator",
        "description": "Operational access to services, providers, catalog, and bookings.",
        "permissions": list(DEFAULT_ROLE_PERMISSIONS["operations_admin"]),
        "is_system": True,
    },
    {
        "slug": "finance_admin",
        "name": "Finance Administrator",
        "description": "Access to payments, transactions, commissions, and withdrawals.",
        "permissions": list(DEFAULT_ROLE_PERMISSIONS["finance_admin"]),
        "is_system": True,
    },
    {
        "slug": "support_admin",
        "name": "Support Administrator",
        "description": "Customer support, booking reviews, and provider verification.",
        "permissions": list(DEFAULT_ROLE_PERMISSIONS["support_admin"]),
        "is_system": True,
    },
    {
        "slug": "viewer",
        "name": "Read-Only Viewer",
        "description": "Read-only access across platform entities.",
        "permissions": list(DEFAULT_ROLE_PERMISSIONS["viewer"]),
        "is_system": True,
    },
]


async def seed(email: str, password: str, full_name: str) -> None:
    now = datetime.now(timezone.utc)
    clean_email = email.strip().lower()

    async with async_session_factory() as session:
        # 1. Seed default system roles
        for meta in DEFAULT_ROLES_META:
            existing_role = await session.execute(
                select(AdminRole).where(AdminRole.slug == meta["slug"])
            )
            if not existing_role.scalar_one_or_none():
                role = AdminRole(
                    id=uuid.uuid4(),
                    slug=meta["slug"],
                    name=meta["name"],
                    description=meta["description"],
                    permissions=meta["permissions"],
                    is_system=meta["is_system"],
                    created_at=now,
                    updated_at=now,
                )
                session.add(role)
                print(f"Created role: {meta['slug']}")

        # 2. Check if user already exists
        user_res = await session.execute(
            select(User).where(User.email == clean_email)
        )
        user = user_res.scalar_one_or_none()

        if not user:
            user = User(
                id=uuid.uuid4(),
                email=clean_email,
                hashed_password=hash_password(password),
                is_active=True,
                is_anonymous=False,
                email_confirmed_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(user)
            await session.flush()
            print(f"Created user: {clean_email} (ID: {user.id})")
        else:
            # Update password
            user.hashed_password = hash_password(password)
            user.is_active = True
            await session.flush()
            print(f"Updated existing user: {clean_email}")

        # 3. Check if Admin record exists
        admin_res = await session.execute(
            select(Admin).where(Admin.user_id == user.id)
        )
        admin = admin_res.scalar_one_or_none()

        if not admin:
            admin = Admin(
                id=uuid.uuid4(),
                user_id=user.id,
                full_name=full_name,
                role="super_admin",
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            session.add(admin)
            print(f"Provisioned super_admin profile for {clean_email}")
        else:
            admin.role = "super_admin"
            admin.is_active = True
            admin.full_name = full_name
            print(f"Updated admin profile for {clean_email}")

        await session.commit()
        print("\nSeed completed successfully!")
        print(f"Login Email:    {clean_email}")
        print(f"Login Password: {password}")
        print(f"Role:           super_admin")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed initial admin and roles")
    parser.add_argument("--email", default="admin@zemen.com", help="Admin email")
    parser.add_argument("--password", default="Admin@123456", help="Admin password")
    parser.add_argument("--name", default="Super Admin", help="Full name")
    args = parser.parse_args()

    asyncio.run(seed(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
