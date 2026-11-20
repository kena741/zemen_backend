"""Seed initial service categories and subcategories for testing and development.

Usage:
    .venv/bin/python scripts/seed_catalog.py
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.persistence.sqlalchemy.connection import async_session_factory
from app.persistence.sqlalchemy.models.catalog import Category, SubCategory
from app.persistence.sqlalchemy.models.finance import Subscription


SEED_DATA = [
    {
        "name": "Plumbing & Piping",
        "description": "Plumbing repair, installation, and maintenance services",
        "subcategories": [
            "Pipe Leak Repair",
            "Drain Cleaning & Unclogging",
            "Water Heater Installation",
        ],
    },
    {
        "name": "Electrical & Wiring",
        "description": "Home and office electrical repairs and wiring",
        "subcategories": [
            "Lighting & Fixtures",
            "Circuit Breaker Repair",
            "Outlet & Switch Installation",
        ],
    },
    {
        "name": "Cleaning & Housekeeping",
        "description": "Residential and commercial cleaning services",
        "subcategories": [
            "Deep Home Cleaning",
            "Office Cleaning",
            "Carpet & Upholstery Cleaning",
        ],
    },
    {
        "name": "Carpentry & Woodwork",
        "description": "Furniture repair, assembly, and custom carpentry",
        "subcategories": [
            "Furniture Assembly & Repair",
            "Door & Window Framing",
            "Cabinet Making",
        ],
    },
]


async def seed_catalog() -> None:
    print("🌱 Seeding categories and subcategories...")
    async with async_session_factory() as session:
        created_count = 0
        for cat_info in SEED_DATA:
            # Check if category exists
            stmt = select(Category).where(Category.category_name == cat_info["name"])
            existing_cat = (await session.execute(stmt)).scalar_one_or_none()

            if not existing_cat:
                cat_id = uuid4()
                cat = Category(
                    id=cat_id,
                    category_name=cat_info["name"],
                    description=cat_info["description"],
                    active=True,
                    image="https://images.unsplash.com/photo-1581578731548-c64695cc6952",
                )
                session.add(cat)
                await session.flush()
                print(f"  [+] Created Category: {cat.category_name} (ID: {cat.id})")
                existing_cat = cat
                created_count += 1
            else:
                print(f"  [=] Category already exists: {existing_cat.category_name} (ID: {existing_cat.id})")

            # Seed subcategories
            for sub_name in cat_info["subcategories"]:
                sub_stmt = select(SubCategory).where(
                    SubCategory.sub_category_name == sub_name,
                    SubCategory.category_id == existing_cat.id,
                )
                existing_sub = (await session.execute(sub_stmt)).scalar_one_or_none()
                if not existing_sub:
                    sub = SubCategory(
                        id=uuid4(),
                        sub_category_name=sub_name,
                        category_id=existing_cat.id,
                        is_free=False,
                    )
                    session.add(sub)
                    await session.flush()
                    print(f"      └── Subcategory: {sub.sub_category_name} (ID: {sub.id})")
                else:
                    print(f"      └── Subcategory exists: {existing_sub.sub_category_name} (ID: {existing_sub.id})")

        # Seed Subscription Plans
        print("\n🌱 Seeding provider subscription plans...")
        plans_data = [
            {"title": "Test Plan", "price": Decimal("10.00"), "service_limit": 2, "description": "Low-cost testing plan (up to 2 services)"},
            {"title": "Starter Plan", "price": Decimal("500.00"), "service_limit": 2, "description": "Create up to 2 active services"},
            {"title": "Growth Plan", "price": Decimal("1000.00"), "service_limit": 5, "description": "Create up to 5 active services"},
            {"title": "Pro Enterprise Plan", "price": Decimal("1800.00"), "service_limit": 10, "description": "Create up to 10 active services"},
        ]
        now = datetime.now(timezone.utc)
        for p in plans_data:
            stmt = select(Subscription).where(Subscription.title == p["title"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                plan = Subscription(
                    title=p["title"],
                    price=p["price"],
                    service_limit=p["service_limit"],
                    description=p["description"],
                    duration="1 Month",
                    plan_type="tier",
                    active=True,
                    is_subscribed=False,
                    created_at=now,
                    updated_at=now,
                )
                session.add(plan)
                await session.flush()
                print(f"  [+] Created Subscription Plan: {plan.title} (ID: {plan.id}, Limit: {plan.service_limit}, Price: {plan.price} ETB)")
            else:
                print(f"  [=] Subscription Plan already exists: {existing.title} (ID: {existing.id})")

        await session.commit()
        print("\n✅ Catalog and plans seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed_catalog())
