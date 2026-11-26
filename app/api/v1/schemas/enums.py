"""Strict literal types for API schemas matching Postgres enum types."""

from typing import Literal

PaymentStatus = Literal[
    "pending_payment",
    "payment_approved_by_admin",
    "payment_rejected_by_admin",
    "payment_completed",
    "payment_cancelled",
]

BookingStatus = Literal[
    "pending",
    "accepted",
    "rejected",
    "declined",
    "cancelled",
    "on_going",
    "on_the_way",
    "in_progress",
    "hold",
    "completed",
    "pending_extra_payment",
    "pending_approval",
    "admin_paid",
]

CompanyVerificationStatus = Literal[
    "not_submitted",
    "pending",
    "approved",
    "rejected",
]

FeatureRequestStatus = Literal[
    "none",
    "pending",
    "rejected",
    "accepted",
]

ProviderType = Literal[
    "individual",
    "company",
]
