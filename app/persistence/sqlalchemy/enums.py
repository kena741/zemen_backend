"""Existing Postgres enum types (owned by Supabase migrations, never created here).

Columns of these types must be mapped with these objects, not `Text`: asyncpg
binds `Text` parameters as `$n::VARCHAR`, and Postgres has no `enum = varchar`
operator or implicit assignment cast.
"""

from sqlalchemy.dialects.postgresql import ENUM


def _existing(name: str, *labels: str) -> ENUM:
    return ENUM(*labels, name=name, create_type=False)


BOOKING_STATUS = _existing(
    "status",
    "pending",
    "accepted",
    "rejected",
    "on_the_way",
    "in_progress",
    "hold",
    "completed",
    "pending_extra_payment",
    "pending_approval",
    "admin_paid",
)

BOOKED_SERVICE_STATUS = _existing(
    "booked_service_status_enum",
    "booked",
    "booked_accepted",
    "booked_rejected",
    "pending_customer_payment",
    "paid_for_service_booked",
    "booked_cancelled",
    "service_started",
    "service_completion_approval",
    "service_completion_approved_by_customer",
)

PAYMENT_STATUS = _existing(
    "payment_status_enum",
    "pending_payment",
    "payment_approved_by_admin",
    "payment_rejected_by_admin",
    "payment_completed",
    "payment_cancelled",
)

FEATURE_REQUEST_STATUS = _existing(
    "feature_request_status_enum", "none", "pending", "rejected", "accepted"
)

PROVIDER_TYPE = _existing("provider_type", "individual", "company")

COMPANY_VERIFICATION_STATUS = _existing(
    "company_verification_status", "not_submitted", "pending", "approved", "rejected"
)

FUNNEL_STAGE = _existing(
    "funnel_stage",
    "Lead",
    "Contacted",
    "Qualified",
    "Proposal",
    "Negotiation",
    "Won",
    "Lost",
)

FEEDBACK_TYPE = _existing("feedback_type", "bug", "idea", "ui-ux", "other")

DOW = _existing(
    "dow",
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
)
