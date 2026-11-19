"""
Shared pytest fixtures for Zemen Backend integration tests.

Architecture
============
• A *session-scoped* async engine prepares the `zemen_test` PostgreSQL database
  and applies the full Alembic migration chain (`alembic upgrade head`) via CLI.
  Running the real Alembic migrations guarantees 100% parity with development,
  staging, and production environments, ensuring that any migration drift or
  missing column bugs are caught immediately without masking them with synthetic DDLs.

• A *function-scoped* `db_session` fixture wraps each test in a SAVEPOINT
  (nested transaction via `join_transaction_mode="create_savepoint"`) over an
  outer connection transaction that is always rolled back on exit.
  No TRUNCATE or manual cleanup is ever needed, ensuring fast, idempotent tests.

• The FastAPI `get_db` dependency is overridden to inject the per-test
  session, so every HTTP call in the test hits the same transaction and sees
  the seeded data.

• JWT helpers sign real tokens with the test JWT secret so that RequireAuth
  / RequireCustomer / RequireProvider / RequireAdmin dependencies work without mocking.

Usage
=====
1. Start the Docker DB:
       docker compose up -d db
2. Create the test database (once):
       docker exec -it zemen-db psql -U postgres -c "CREATE DATABASE zemen_test;"
3. Run tests:
       pytest tests/integration/ -v
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator
from uuid import UUID, uuid4

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api import create_app
from app.config import settings
from app.persistence.sqlalchemy.base import Base
from app.persistence.sqlalchemy.deps import get_db

# ---------------------------------------------------------------------------
# Map all models into the metadata so create_all() knows about every table
# ---------------------------------------------------------------------------
from app.persistence.sqlalchemy.map_registry import init_mapper  # noqa: E402

init_mapper()

# ---------------------------------------------------------------------------
# Test database URL — same Postgres host, separate database
# ---------------------------------------------------------------------------
TEST_DB_URL = (
    settings.DEVELOPMENT_DATABASE_URL.replace(
        "/zemen_db", "/zemen_test"
    )
)


# ---------------------------------------------------------------------------
# Event-loop (session-scoped) — required by pytest-asyncio
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Database schema initialization via real Alembic migrations
# ---------------------------------------------------------------------------
def _apply_alembic_migrations() -> None:
    """
    Applies the real Alembic migration chain to the test database via CLI.
    Running in a subprocess ensures the Alembic asyncio event loop does not
    conflict with pytest's active session loop.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = dict(
        os.environ,
        ENVIRONMENT="development",
        DEVELOPMENT_DATABASE_URL=TEST_DB_URL,
    )
    root = Path(__file__).resolve().parent.parent
    alembic_bin = sys.executable.replace("python", "alembic")
    if not Path(alembic_bin).exists():
        alembic_bin = "alembic"

    res = subprocess.run(
        [alembic_bin, "-c", "app/persistence/sqlalchemy/alembic.ini", "upgrade", "head"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        raise RuntimeError(
            f"Alembic migration failed on test DB:\n{res.stdout}\n{res.stderr}"
        )


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    # Run all real Alembic migrations against the test database
    _apply_alembic_migrations()

    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


# ---------------------------------------------------------------------------
# Session factory — session-scoped
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture(scope="session")
async def test_session_factory(test_engine):
    return async_sessionmaker(
        test_engine,
        expire_on_commit=False,
        autoflush=False,
        class_=AsyncSession,
    )


# ---------------------------------------------------------------------------
# DB session — function-scoped, rolled back after every test
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Yields a session bound to a connection wrapped in an outer transaction.
    Uses join_transaction_mode="create_savepoint" so that even if the app code
    or endpoint calls session.commit(), it only releases a SAVEPOINT.
    The outer transaction is always rolled back in finally, guaranteeing 100%
    idempotent and isolated tests with zero persistent changes.
    """
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


# ---------------------------------------------------------------------------
# HTTP client — function-scoped, overrides get_db
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient wired to the test session via FastAPI dependency override."""
    app = create_app()

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def _make_token(user_id: UUID, email: str | None = None, role: str = "authenticated") -> str:
    """Sign a test JWT using the app's configured secret."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Seed helpers — insert rows and return domain-compatible dicts
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def seed_user(db_session: AsyncSession):
    """
    Factory fixture: call it with keyword args to create a User row.
    Returns a (user_id, hashed_password_plaintext) tuple so callers can build
    further fixtures or craft login payloads.
    """
    from app.persistence.sqlalchemy.models.users import User

    async def _create(
        phone: str | None = None,
        email: str | None = None,
        password: str = "TestPass123!",
    ) -> tuple[UUID, str]:
        from app.core.auth.hashing import hash_password

        if phone is None:
            phone = f"+2519{secrets.randbelow(90000000) + 10000000}"

        hashed = hash_password(password)
        user = User(
            id=uuid4(),
            phone=phone,
            email=email,
            hashed_password=hashed,
            is_active=True,
            is_anonymous=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        await db_session.flush()
        return user.id, password

    return _create


@pytest_asyncio.fixture
async def seed_customer(db_session: AsyncSession, seed_user):
    """
    Factory: creates a User + Customer row.
    Returns (customer_obj, user_id, plain_password, jwt_token).
    """
    from app.persistence.sqlalchemy.models.identity import Customer

    async def _create(
        phone: str | None = None,
        email: str | None = None,
        password: str = "TestPass123!",
        first_name: str = "Test",
        last_name: str = "Customer",
    ):
        if phone is None:
            phone = f"+2519{secrets.randbelow(90000000) + 10000000}"
        user_id, plain_pw = await seed_user(phone=phone, email=email, password=password)
        cust = Customer(
            id=uuid4(),
            user_id=user_id,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            created_at=datetime.now(timezone.utc),
            active=True,
        )
        db_session.add(cust)
        await db_session.flush()
        token = _make_token(user_id, email=email, role="authenticated")
        return cust, user_id, plain_pw, token

    return _create


@pytest_asyncio.fixture
async def seed_provider(db_session: AsyncSession, seed_user):
    """
    Factory: creates a User + Provider row.
    Returns (provider_obj, user_id, plain_password, jwt_token).
    """
    from app.persistence.sqlalchemy.models.identity import Provider

    async def _create(
        phone: str | None = None,
        email: str | None = None,
        password: str = "TestPass123!",
        first_name: str = "Test",
        last_name: str = "Provider",
    ):
        if phone is None:
            phone = f"+2519{secrets.randbelow(90000000) + 10000000}"
        user_id, plain_pw = await seed_user(phone=phone, email=email, password=password)
        prov = Provider(
            id=uuid4(),
            user_id=user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone,
            active=True,
            activation_paid=False,
            service_tier_max=0,
            verified_subcategory_ids=[],
            social_links={},
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(prov)
        await db_session.flush()
        token = _make_token(user_id, email=email, role="authenticated")
        return prov, user_id, plain_pw, token

    return _create


@pytest_asyncio.fixture
async def seed_category(db_session: AsyncSession):
    """Factory: inserts a Category row and returns it."""
    from app.persistence.sqlalchemy.models.catalog import Category

    async def _create(
        name: str = "Cleaning",
        active: bool = True,
        description: str | None = "Home cleaning services",
    ) -> Category:
        cat = Category(
            id=uuid4(),
            category_name=name,
            active=active,
            description=description,
        )
        db_session.add(cat)
        await db_session.flush()
        return cat

    return _create


@pytest_asyncio.fixture
async def seed_subcategory(db_session: AsyncSession):
    """Factory: inserts a SubCategory row and returns it."""
    from app.persistence.sqlalchemy.models.catalog import SubCategory

    async def _create(
        category_id: UUID | None = None,
        name: str = "Deep Cleaning",
        is_free: bool = False,
    ) -> SubCategory:
        sub = SubCategory(
            id=uuid4(),
            sub_category_name=name,
            category_id=category_id or uuid4(),
            is_free=is_free,
        )
        db_session.add(sub)
        await db_session.flush()
        return sub

    return _create


@pytest_asyncio.fixture
async def seed_document(db_session: AsyncSession):
    """Factory: inserts a Document row and returns it."""
    from app.persistence.sqlalchemy.models.admin import Document

    async def _create(
        name: str = "National ID",
        active: bool = True,
        description: str | None = "Government-issued photo ID",
    ):
        doc = Document(
            id=uuid4(),
            name=name,
            active=active,
            description=description,
        )
        db_session.add(doc)
        await db_session.flush()
        return doc

    return _create


@pytest_asyncio.fixture
async def seed_service(db_session: AsyncSession):
    """Factory: inserts an approved, active Service row and returns it."""
    from app.persistence.sqlalchemy.models.catalog import Service

    async def _create(
        provider_id: UUID | None = None,
        category_id: UUID | None = None,
        sub_category_id: UUID | None = None,
        service_name: str = "House Cleaning",
        price: Decimal = Decimal("500.00"),
        approved: bool = True,
        is_archived: bool = False,
        status: bool = True,
        allows_custom_offer: bool = False,
    ) -> Service:
        pid = provider_id or uuid4()
        cid = category_id or uuid4()
        scid = sub_category_id or uuid4()
        svc = Service(
            id=uuid4(),
            provider_id=pid,
            service_name=service_name,
            description="Professional house cleaning",
            category_id=cid,
            category_model={"id": str(cid), "categoryName": "Cleaning"},
            sub_category_id=scid,
            sub_category_model={"id": str(scid), "subCategoryName": "Deep Cleaning"},
            type="fixed",
            service_location_mode="on_site",
            price=price,
            pre_payment=False,
            feature=False,
            status=status,
            active=True,
            service_image=["https://example.com/img.jpg"],
            created_at=datetime.now(timezone.utc),
            approved=approved,
            allows_custom_offer=allows_custom_offer,
            pricing_type="fixed",
            is_archived=is_archived,
            liked_user=[],
            liked_users=[],
            position=None,
        )
        db_session.add(svc)
        await db_session.flush()
        return svc

    return _create


@pytest_asyncio.fixture
async def seed_booking(db_session: AsyncSession):
    """Factory: inserts a BookedService row and returns it."""
    from app.persistence.sqlalchemy.models.booking import BookedService

    async def _create(
        provider_id: UUID | None = None,
        customer_id: UUID | None = None,
        service_id: UUID | None = None,
        status: str = "pending",
        payment_status: str = "pending_payment",
        otp: str | None = None,
    ) -> BookedService:
        bk = BookedService(
            id=uuid4(),
            provider_id=provider_id or uuid4(),
            customer_id=customer_id,
            service_id=service_id,
            service_name="House Cleaning",
            first_name="Test",
            last_name="Customer",
            phone_number=f"+2519{secrets.randbelow(90000000) + 10000000}",
            price=Decimal("500.00"),
            total_amount=Decimal("550.00"),
            sub_total=Decimal("500.00"),
            tax_list=[],
            quantity=1,
            booking_date=datetime.now(timezone.utc) + timedelta(days=1),
            payment_completed=False,
            status=status,
            payment_status=payment_status,
            otp=otp,
            created_at=datetime.now(timezone.utc),
            is_archived=False,
            next_cycle_due=False,
            post_job_payment=False,
            provider_myself=False,
            pre_payment_extra_charge_payment=False,
        )
        db_session.add(bk)
        await db_session.flush()
        return bk

    return _create


# ---------------------------------------------------------------------------
# Convenience: pre-built authenticated customer + provider HTTP clients
# ---------------------------------------------------------------------------
@pytest_asyncio.fixture
async def customer_client(client: AsyncClient, seed_customer):
    """Returns (async_client_with_auth_headers, customer_obj)."""
    cust, user_id, _, token = await seed_customer()
    client.headers.update(_auth_headers(token))
    return client, cust


@pytest_asyncio.fixture
async def provider_client(client: AsyncClient, seed_provider):
    """Returns (async_client_with_auth_headers, provider_obj)."""
    prov, user_id, _, token = await seed_provider()
    client.headers.update(_auth_headers(token))
    return client, prov


@pytest_asyncio.fixture
async def seed_admin(db_session: AsyncSession, seed_user):
    """Factory: inserts AdminRole and Admin row and returns (admin_obj, user_id, email, token)."""
    from sqlalchemy import select
    from app.persistence.sqlalchemy.models.admin import Admin, AdminRole

    async def _create(
        email: str | None = None,
        role_slug: str = "superadmin",
        permissions: list[str] | None = None,
    ):
        if permissions is None:
            permissions = ["*"]
        if email is None:
            email = f"admin_{secrets.token_hex(4)}@example.com"

        user_id, pwd = await seed_user(email=email)

        # Check or create AdminRole
        stmt = select(AdminRole).where(AdminRole.slug == role_slug)
        existing_role = (await db_session.execute(stmt)).scalar_one_or_none()
        if not existing_role:
            admin_role = AdminRole(
                id=uuid4(),
                slug=role_slug,
                name="Super Admin",
                description="All permissions",
                permissions=permissions,
                is_system=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db_session.add(admin_role)
            await db_session.flush()

        admin = Admin(
            id=uuid4(),
            user_id=user_id,
            full_name="Admin Test",
            role=role_slug,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(admin)
        await db_session.flush()

        token = _make_token(user_id=user_id, email=email, role="authenticated")
        return admin, user_id, email, token

    return _create


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, seed_admin):
    """Returns (async_client_with_admin_auth_headers, admin_obj)."""
    admin, user_id, email, token = await seed_admin()
    client.headers.update(_auth_headers(token))
    return client, admin

