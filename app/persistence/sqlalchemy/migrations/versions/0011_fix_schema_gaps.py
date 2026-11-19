"""Fix schema gaps between ORM models and existing migrations.

Adds columns that the ORM models reference but earlier migrations
omitted or named differently, relaxes legacy NOT NULL constraints on unused
columns, and registers missing enum values.

All additions use ADD COLUMN IF NOT EXISTS so this migration is safe to
re-run on databases that were partially patched.

Revision ID: 0011_fix_schema_gaps
Revises: 0010_align_identity_schema
Create Date: 2026-11-18 17:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_fix_schema_gaps"
down_revision: Union[str, Sequence[str], None] = "0010_align_identity_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. category ──────────────────────────────────────────────────────────
    # Migration 0003 created the column as `title` (NOT NULL).
    # The ORM model maps category_name → "categoryName".
    op.execute(
        sa.text('ALTER TABLE category ADD COLUMN IF NOT EXISTS "categoryName" TEXT')
    )
    op.execute(
        sa.text(
            """
            UPDATE category
            SET "categoryName" = title
            WHERE "categoryName" IS NULL AND title IS NOT NULL
            """
        )
    )
    # Relax legacy NOT NULL columns so ORM insert succeeds without them
    for col in ("title", "image", "active", '"createdAt"', "is_featured"):
        op.execute(
            sa.text(f"ALTER TABLE category ALTER COLUMN {col} DROP NOT NULL")
        )

    # ── 2. sub_category ───────────────────────────────────────────────────────
    # Migration 0003 called it `title` (NOT NULL). ORM expects "subCategoryName".
    op.execute(
        sa.text('ALTER TABLE sub_category ADD COLUMN IF NOT EXISTS "subCategoryName" TEXT')
    )
    op.execute(
        sa.text(
            """
            UPDATE sub_category
            SET "subCategoryName" = title
            WHERE "subCategoryName" IS NULL AND title IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text('ALTER TABLE sub_category ADD COLUMN IF NOT EXISTS "isFree" BOOLEAN NOT NULL DEFAULT FALSE')
    )
    for col in ("title", "image", "active", '"createdAt"'):
        op.execute(
            sa.text(f"ALTER TABLE sub_category ALTER COLUMN {col} DROP NOT NULL")
        )

    # ── 3. banner ────────────────────────────────────────────────────────────
    # Migration 0007 created banner_name; ORM expects "bannerName".
    op.execute(
        sa.text('ALTER TABLE banner ADD COLUMN IF NOT EXISTS "bannerName" TEXT')
    )
    op.execute(
        sa.text(
            """
            UPDATE banner
            SET "bannerName" = banner_name
            WHERE "bannerName" IS NULL AND banner_name IS NOT NULL
            """
        )
    )

    # ── 4. documents ─────────────────────────────────────────────────────────
    # Migration 0002 omitted `description`.
    op.execute(
        sa.text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS description TEXT")
    )

    # ── 5. service ───────────────────────────────────────────────────────────
    # ORM model has `position` (JSONB) and `liked_users` (UUID[]).
    op.execute(
        sa.text("ALTER TABLE service ADD COLUMN IF NOT EXISTS position JSONB")
    )
    op.execute(
        sa.text("ALTER TABLE service ADD COLUMN IF NOT EXISTS liked_users UUID[]")
    )

    # ── 6. sub_category_documents ────────────────────────────────────────────
    op.execute(
        sa.text('ALTER TABLE sub_category_documents ADD COLUMN IF NOT EXISTS "subCategoryId" UUID')
    )
    op.execute(
        sa.text('ALTER TABLE sub_category_documents ADD COLUMN IF NOT EXISTS "documentId" UUID')
    )
    op.execute(
        sa.text('ALTER TABLE sub_category_documents ADD COLUMN IF NOT EXISTS "isRequired" BOOLEAN DEFAULT FALSE')
    )
    op.execute(
        sa.text("ALTER TABLE sub_category_documents ADD COLUMN IF NOT EXISTS description TEXT")
    )

    # ── 7. verify_documents ──────────────────────────────────────────────────
    op.execute(
        sa.text('ALTER TABLE verify_documents ADD COLUMN IF NOT EXISTS "providerName" TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE verify_documents ADD COLUMN IF NOT EXISTS "providerEmail" TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE verify_documents ADD COLUMN IF NOT EXISTS "documentImage" TEXT')
    )

    # ── 8. admin_documents ───────────────────────────────────────────────────
    op.execute(
        sa.text("ALTER TABLE admin_documents ADD COLUMN IF NOT EXISTS title TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE admin_documents ADD COLUMN IF NOT EXISTS file_name TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE admin_documents ALTER COLUMN name DROP NOT NULL")
    )
    op.execute(
        sa.text("ALTER TABLE admin_documents ALTER COLUMN file_size_bytes DROP NOT NULL")
    )

    # ── 9. bank_details ──────────────────────────────────────────────────────
    for col in (
        '"accountNumber"',
        '"bankName"',
        '"branchCity"',
        '"branchCountry"',
        '"holderName"',
        '"swiftCode"',
    ):
        op.execute(
            sa.text(f"ALTER TABLE bank_details ADD COLUMN IF NOT EXISTS {col} TEXT")
        )
    op.execute(
        sa.text('ALTER TABLE bank_details ADD COLUMN IF NOT EXISTS "providerID" UUID')
    )
    for col in ("bank_name", "account_number", "account_holder_name"):
        op.execute(
            sa.text(f"ALTER TABLE bank_details ALTER COLUMN {col} DROP NOT NULL")
        )

    # ── 10. wallet_transaction ───────────────────────────────────────────────
    op.execute(
        sa.text('ALTER TABLE wallet_transaction ADD COLUMN IF NOT EXISTS "createdDate" TIMESTAMPTZ DEFAULT now()')
    )
    op.execute(
        sa.text('ALTER TABLE wallet_transaction ADD COLUMN IF NOT EXISTS "isCredit" BOOLEAN DEFAULT FALSE')
    )
    op.execute(
        sa.text("ALTER TABLE wallet_transaction ADD COLUMN IF NOT EXISTS note TEXT")
    )
    op.execute(
        sa.text('ALTER TABLE wallet_transaction ADD COLUMN IF NOT EXISTS "paymentType" TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE wallet_transaction ADD COLUMN IF NOT EXISTS "transactionId" TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE wallet_transaction ADD COLUMN IF NOT EXISTS "userId" UUID')
    )
    op.execute(
        sa.text("ALTER TABLE wallet_transaction ALTER COLUMN user_id DROP NOT NULL")
    )
    op.execute(
        sa.text("ALTER TABLE wallet_transaction ALTER COLUMN created_at DROP NOT NULL")
    )

    # ── 11. withdrawal_history ───────────────────────────────────────────────
    for col in (
        '"adminNote"',
        "note",
        '"paymentDate"',
        '"paymentMethodId"',
        '"holderName"',
        '"bankName"',
        '"accountNumber"',
        '"swiftCode"',
        '"rejectionReason"',
    ):
        op.execute(
            sa.text(f"ALTER TABLE withdrawal_history ADD COLUMN IF NOT EXISTS {col} TEXT")
        )
    op.execute(
        sa.text('ALTER TABLE withdrawal_history ADD COLUMN IF NOT EXISTS "createdDate" TIMESTAMPTZ DEFAULT now()')
    )

    # ── 12. notifications ────────────────────────────────────────────────────
    op.execute(
        sa.text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS body TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS is_read BOOLEAN DEFAULT FALSE")
    )
    op.execute(
        sa.text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS request_id UUID")
    )
    op.execute(
        sa.text('ALTER TABLE notifications ADD COLUMN IF NOT EXISTS "bookingId" UUID')
    )
    op.execute(
        sa.text('ALTER TABLE notifications ADD COLUMN IF NOT EXISTS "customerId" UUID')
    )
    op.execute(
        sa.text("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS description TEXT")
    )
    op.execute(
        sa.text('ALTER TABLE notifications ADD COLUMN IF NOT EXISTS "handymanId" UUID')
    )
    op.execute(
        sa.text('ALTER TABLE notifications ADD COLUMN IF NOT EXISTS "providerId" UUID')
    )
    op.execute(
        sa.text('ALTER TABLE notifications ADD COLUMN IF NOT EXISTS "senderId" UUID')
    )
    op.execute(
        sa.text("ALTER TABLE notifications ALTER COLUMN read DROP NOT NULL")
    )
    op.execute(
        sa.text("ALTER TABLE notifications ALTER COLUMN message DROP NOT NULL")
    )

    # ── 13. job_request ──────────────────────────────────────────────────────
    op.execute(
        sa.text('ALTER TABLE job_request ADD COLUMN IF NOT EXISTS "createdAt" TIMESTAMPTZ DEFAULT now()')
    )
    op.execute(
        sa.text('ALTER TABLE job_request ADD COLUMN IF NOT EXISTS "bidList" JSONB[]')
    )
    op.execute(
        sa.text('ALTER TABLE job_request ADD COLUMN IF NOT EXISTS "bidPrice" TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE job_request ADD COLUMN IF NOT EXISTS "customerId" UUID')
    )
    op.execute(
        sa.text('ALTER TABLE job_request ADD COLUMN IF NOT EXISTS "handymanId" TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE job_request ADD COLUMN IF NOT EXISTS "providerId" UUID')
    )
    op.execute(
        sa.text('ALTER TABLE job_request ADD COLUMN IF NOT EXISTS "serviceId" UUID')
    )
    op.execute(
        sa.text('ALTER TABLE job_request ADD COLUMN IF NOT EXISTS "serviceModelList" JSONB[]')
    )
    op.execute(
        sa.text("ALTER TABLE job_request ALTER COLUMN created_at DROP NOT NULL")
    )

    # ── 14. service_offer ────────────────────────────────────────────────────
    op.execute(
        sa.text("ALTER TABLE service_offer ADD COLUMN IF NOT EXISTS offered_price NUMERIC")
    )
    op.execute(
        sa.text("ALTER TABLE service_offer ADD COLUMN IF NOT EXISTS message TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE service_offer ADD COLUMN IF NOT EXISTS booking_id TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE service_offer ADD COLUMN IF NOT EXISTS booking_date TIMESTAMPTZ")
    )
    op.execute(
        sa.text("ALTER TABLE service_offer ADD COLUMN IF NOT EXISTS booking_address JSONB")
    )
    op.execute(
        sa.text("ALTER TABLE service_offer ADD COLUMN IF NOT EXISTS service_description TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE service_offer ALTER COLUMN offer_price DROP NOT NULL")
    )
    op.execute(
        sa.text("ALTER TABLE service_offer ALTER COLUMN service_id TYPE TEXT USING service_id::TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE service_offer ALTER COLUMN customer_id TYPE TEXT USING customer_id::TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE service_offer ALTER COLUMN provider_id TYPE TEXT USING provider_id::TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE service_offer ALTER COLUMN booking_id TYPE TEXT USING booking_id::TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE service_offer ALTER COLUMN booking_address TYPE JSONB USING booking_address::JSONB")
    )

    # ── 15. status enum values ───────────────────────────────────────────────
    # Booking lifecycle service transitions to 'declined', 'cancelled', 'on_going'.
    for val in ("declined", "cancelled", "on_going"):
        op.execute(
            sa.text(f"ALTER TYPE status ADD VALUE IF NOT EXISTS '{val}'")
        )

    # ── 16. customer_service_details ─────────────────────────────────────────
    op.execute(
        sa.text("ALTER TABLE customer_service_details ADD COLUMN IF NOT EXISTS service_images TEXT[]")
    )
    op.execute(
        sa.text(
            """
            UPDATE customer_service_details
            SET service_images = service_image
            WHERE service_images IS NULL AND service_image IS NOT NULL
            """
        )
    )
    for col, col_type in [
        ("category_name", "TEXT"),
        ("category_active", "BOOLEAN"),
        ("category_image", "TEXT"),
        ("category_model_id", "TEXT"),
        ("sub_category_model", "JSONB"),
        ("create_at", "TIMESTAMPTZ"),
        ("location_latitude", "DOUBLE PRECISION"),
        ("location_longitude", "DOUBLE PRECISION"),
        ("position_geohash", "TEXT"),
        ("position_geopoint", "JSONB"),
    ]:
        op.execute(
            sa.text(f"ALTER TABLE customer_service_details ADD COLUMN IF NOT EXISTS {col} {col_type}")
        )
    for col in ("category_id", "sub_category_id", "provider_id"):
        op.execute(
            sa.text(f"ALTER TABLE customer_service_details ALTER COLUMN {col} TYPE TEXT USING {col}::TEXT")
        )
    op.execute(
        sa.text("ALTER TABLE customer_service_details ALTER COLUMN status TYPE TEXT USING status::TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE customer_service_details ALTER COLUMN feature TYPE JSONB USING to_jsonb(feature)")
    )
    op.execute(
        sa.text("ALTER TABLE customer_service_details ALTER COLUMN liked_user TYPE JSONB USING to_jsonb(liked_user)")
    )

    # ── 17. companies ─────────────────────────────────────────────────────────
    for col in ("owner_user_id", "verification_status"):
        op.execute(
            sa.text(f"ALTER TABLE companies ALTER COLUMN {col} DROP NOT NULL")
        )

    # ── 18. provider_payment_methods ─────────────────────────────────────────
    op.execute(
        sa.text("ALTER TABLE provider_payment_methods ADD COLUMN IF NOT EXISTS method_type TEXT NOT NULL DEFAULT 'bank'")
    )
    op.execute(
        sa.text("ALTER TABLE provider_payment_methods ADD COLUMN IF NOT EXISTS method_code TEXT DEFAULT 'bank'")
    )
    op.execute(
        sa.text("ALTER TABLE provider_payment_methods ADD COLUMN IF NOT EXISTS method_name TEXT DEFAULT 'Bank Account'")
    )
    for col in ('"holderName"', '"swiftCode"', '"branchCity"', '"branchCountry"'):
        op.execute(
            sa.text(f"ALTER TABLE provider_payment_methods ADD COLUMN IF NOT EXISTS {col} TEXT")
        )
    op.execute(
        sa.text("ALTER TABLE provider_payment_methods ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
    )
    op.execute(
        sa.text("ALTER TABLE provider_payment_methods ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE")
    )
    op.execute(
        sa.text("ALTER TABLE provider_payment_methods ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'::jsonb")
    )
    op.execute(
        sa.text("ALTER TABLE provider_payment_methods ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()")
    )
    op.execute(
        sa.text("ALTER TABLE provider_payment_methods ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()")
    )
    for col in ('"bankID"', '"accountHolderName"', '"isDefault"', '"createdAt"', '"updatedAt"'):
        op.execute(
            sa.text(f"ALTER TABLE provider_payment_methods ALTER COLUMN {col} DROP NOT NULL")
        )

    # ── 19. admin table defaults ──────────────────────────────────────────────
    op.execute(
        sa.text("ALTER TABLE admin ALTER COLUMN created_at SET DEFAULT now()")
    )
    op.execute(
        sa.text("ALTER TABLE admin ALTER COLUMN updated_at SET DEFAULT now()")
    )

    # ── 20. review_customer ──────────────────────────────────────────────────
    op.execute(
        sa.text("ALTER TABLE review_customer ADD COLUMN IF NOT EXISTS comment TEXT")
    )
    op.execute(
        sa.text(
            """
            UPDATE review_customer
            SET comment = review
            WHERE comment IS NULL AND review IS NOT NULL
            """
        )
    )
    op.execute(
        sa.text('ALTER TABLE review_customer ADD COLUMN IF NOT EXISTS date TIMESTAMPTZ DEFAULT now()')
    )
    op.execute(
        sa.text('ALTER TABLE review_customer ADD COLUMN IF NOT EXISTS "bookingId" UUID')
    )
    op.execute(
        sa.text("ALTER TABLE review_customer ALTER COLUMN rating TYPE TEXT USING rating::TEXT")
    )

    # ── 21. notification (singular) ──────────────────────────────────────────
    op.execute(
        sa.text("ALTER TABLE notification ADD COLUMN IF NOT EXISTS description TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE notification ADD COLUMN IF NOT EXISTS sender_id UUID")
    )
    op.execute(
        sa.text("ALTER TABLE notification ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ")
    )
    op.execute(
        sa.text("ALTER TABLE notification ADD COLUMN IF NOT EXISTS action_url TEXT")
    )
    op.execute(
        sa.text("ALTER TABLE notification ADD COLUMN IF NOT EXISTS recipient_role TEXT DEFAULT 'customer'")
    )
    op.execute(
        sa.text("ALTER TABLE notification ALTER COLUMN created_at DROP NOT NULL")
    )

    # ── 22. chat and chat_inbox ──────────────────────────────────────────────
    op.execute(
        sa.text('ALTER TABLE chat ALTER COLUMN id SET DEFAULT gen_random_uuid()')
    )
    op.execute(
        sa.text('ALTER TABLE chat ADD COLUMN IF NOT EXISTS "chatID" TEXT DEFAULT gen_random_uuid()::TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE chat ADD COLUMN IF NOT EXISTS "mediaUrl" TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE chat ADD COLUMN IF NOT EXISTS seen BOOLEAN DEFAULT FALSE')
    )
    op.execute(
        sa.text('ALTER TABLE chat ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ DEFAULT now()')
    )
    op.execute(
        sa.text("ALTER TABLE chat ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'text'")
    )
    op.execute(
        sa.text('ALTER TABLE chat ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()')
    )
    op.execute(
        sa.text('ALTER TABLE chat ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()')
    )
    op.execute(
        sa.text('ALTER TABLE chat ALTER COLUMN "senderId" TYPE TEXT USING "senderId"::TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE chat ALTER COLUMN "receiverId" TYPE TEXT USING "receiverId"::TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE chat ALTER COLUMN "isRead" DROP NOT NULL')
    )
    op.execute(
        sa.text('ALTER TABLE chat ALTER COLUMN "createdAt" DROP NOT NULL')
    )

    op.execute(
        sa.text('ALTER TABLE chat_inbox ALTER COLUMN id TYPE TEXT USING id::TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE chat_inbox ALTER COLUMN "senderId" TYPE TEXT USING "senderId"::TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE chat_inbox ALTER COLUMN "receiverId" TYPE TEXT USING "receiverId"::TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE chat_inbox ADD COLUMN IF NOT EXISTS "mediaUrl" TEXT')
    )
    op.execute(
        sa.text('ALTER TABLE chat_inbox ADD COLUMN IF NOT EXISTS seen BOOLEAN DEFAULT FALSE')
    )
    op.execute(
        sa.text("ALTER TABLE chat_inbox ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'text'")
    )
    op.execute(
        sa.text('ALTER TABLE chat_inbox ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ DEFAULT now()')
    )
    op.execute(
        sa.text('ALTER TABLE chat_inbox ADD COLUMN IF NOT EXISTS archive BOOLEAN DEFAULT FALSE')
    )
    op.execute(
        sa.text('ALTER TABLE chat_inbox ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now()')
    )
    op.execute(
        sa.text('ALTER TABLE chat_inbox ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()')
    )
    op.execute(
        sa.text('ALTER TABLE chat_inbox ALTER COLUMN "createdAt" DROP NOT NULL')
    )
    op.execute(
        sa.text('ALTER TABLE chat_inbox ALTER COLUMN "unreadCount" DROP NOT NULL')
    )








def downgrade() -> None:
    pass
