"""Admin read DTOs (Plan 6c). Field aliases follow the column names lolelink-admin renders."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.admin import AdminServiceOut
from app.api.v1.schemas.booking import BookingOut
from app.api.v1.schemas.common import APIModel
from app.api.v1.schemas.customer import CustomerOut
from app.api.v1.schemas.provider import ProviderOut
from app.api.v1.schemas.wallet import WithdrawalOut


class AdminCustomerOut(CustomerOut):
    login_type: str | None = None
    signup_source: str | None = None
    archived_at: datetime | None = None
    booking_count: int = Field(default=0, serialization_alias="bookingCount")
    last_booking_at: datetime | None = Field(default=None, serialization_alias="lastBookingAt")
    is_provider: bool = Field(default=False, serialization_alias="isProvider")


class AdminProviderOut(ProviderOut):
    user_type: str | None = Field(default=None, serialization_alias="userType")
    location: Any | None = None
    social_links: Any | None = Field(default=None, serialization_alias="socialLinks")
    activation_paid_at: datetime | None = None
    activation_tx_ref: str | None = None
    service_tier_paid_at: datetime | None = None
    verified_subcategory_ids: list[UUID] = Field(default_factory=list)
    signup_source: str | None = Field(default=None, serialization_alias="signupSource")
    archived_at: datetime | None = None
    updated_at: datetime | None = Field(default=None, serialization_alias="updateAt")
    service_count: int = Field(default=0, serialization_alias="serviceCount")


class AdminServiceListItem(AdminServiceOut):
    provider_name: str = Field(default="", serialization_alias="providerName")
    provider_location: Any | None = Field(default=None, serialization_alias="providerLocation")
    feature_request_paid: bool = Field(default=False, serialization_alias="featureRequestPaid")
    feature_request_paid_amount: str | None = Field(default=None, serialization_alias="featureRequestPaidAmount")
    feature_request_transaction_id: str | None = Field(
        default=None, serialization_alias="featureRequestTransactionId"
    )


class AdminBookingOut(BookingOut):
    reason: str | None = None
    payment_id: UUID | None = None
    provider_user_id: UUID | None = None
    customer_user_id: UUID | None = None
    country_code: str | None = Field(default=None, serialization_alias="countryCode")
    tax_list: Any | None = Field(default=None, serialization_alias="taxList")
    service_details: Any | None = Field(default=None, serialization_alias="serviceDetails")
    service_proof: Any | None = None
    pre_payment_extra_charge_payment: bool = Field(serialization_alias="prePaymentExtraChargePayment")
    post_job_payment: bool = Field(serialization_alias="postJobPayment")
    provider_myself: bool = Field(serialization_alias="providerMySelf")
    provider_name: str | None = Field(default=None, serialization_alias="providerName")
    customer_name: str | None = Field(default=None, serialization_alias="customerName")


class AdminWithdrawalOut(WithdrawalOut):
    admin_note: str | None = Field(default=None, serialization_alias="adminNote")
    payment_date: str | None = Field(default=None, serialization_alias="paymentDate")
    payment_method_id: str | None = Field(default=None, serialization_alias="paymentMethodId")
    swift_code: str | None = Field(default=None, serialization_alias="swiftCode")
    provider_name: str | None = Field(default=None, serialization_alias="providerName")


class PaymentMethodOut(APIModel):
    id: UUID
    provider_id: UUID | None = Field(default=None, serialization_alias="providerID")
    method_type: str | None = None
    method_code: str | None = None
    method_name: str | None = None
    holder_name: str | None = Field(default=None, serialization_alias="holderName")
    account_number: str | None = Field(default=None, serialization_alias="accountNumber")
    swift_code: str | None = Field(default=None, serialization_alias="swiftCode")
    bank_name: str | None = Field(default=None, serialization_alias="bankName")
    branch_city: str | None = Field(default=None, serialization_alias="branchCity")
    branch_country: str | None = Field(default=None, serialization_alias="branchCountry")
    is_active: bool | None = None
    is_default: bool | None = None
    currency: str | None = None
    updated_at: datetime | None = None


class AdminWithdrawalDetail(AdminWithdrawalOut):
    payment_methods: list[PaymentMethodOut] = Field(default_factory=list, serialization_alias="paymentMethods")


class CountWindow(APIModel):
    total: int
    last_30_days: int = Field(serialization_alias="last30Days")


class DashboardSummary(APIModel):
    """Sections are omitted (null) when the admin lacks the matching read permission."""

    bookings_by_status: dict[str, int] | None = Field(default=None, serialization_alias="bookingsByStatus")
    bookings: CountWindow | None = None
    customers: CountWindow | None = None
    providers: CountWindow | None = None
    services_pending_approval: int | None = Field(default=None, serialization_alias="servicesPendingApproval")
    feature_requests_pending: int | None = Field(default=None, serialization_alias="featureRequestsPending")
    documents_pending: int | None = Field(default=None, serialization_alias="documentsPending")
    job_requests: CountWindow | None = Field(default=None, serialization_alias="jobRequests")
    withdrawals_by_status: dict[str, int] | None = Field(default=None, serialization_alias="withdrawalsByStatus")
    withdrawals_pending_amount: Decimal | None = Field(default=None, serialization_alias="withdrawalsPendingAmount")
    completed_booking_revenue: Decimal | None = Field(default=None, serialization_alias="completedBookingRevenue")


class LedgerHealth(APIModel):
    total_rows: int = Field(serialization_alias="totalRows")
    non_numeric_amounts: int = Field(serialization_alias="nonNumericAmounts")
    untyped_rows: int = Field(serialization_alias="untypedRows")
    orphan_customer_rows: int = Field(serialization_alias="orphanCustomerRows")
    orphan_provider_rows: int = Field(serialization_alias="orphanProviderRows")
    non_numeric_provider_balances: int = Field(serialization_alias="nonNumericProviderBalances")


class DuplicateCredit(APIModel):
    transaction_id: str = Field(serialization_alias="transactionId")
    type: str | None = None
    amount: str
    note: str | None = None
    copies: int
    first_at: datetime | None = Field(default=None, serialization_alias="firstAt")
    last_at: datetime | None = Field(default=None, serialization_alias="lastAt")
    excess_amount: Decimal = Field(serialization_alias="excessAmount")


class BalanceDrift(APIModel):
    account_id: UUID = Field(serialization_alias="accountId")
    balance: Decimal
    ledger_net: Decimal = Field(serialization_alias="ledgerNet")
    drift: Decimal
    ledger_rows: int = Field(serialization_alias="ledgerRows")


class ReconciliationReport(APIModel):
    """Read-only. A wallet balance should equal credits minus debits in `wallet_transaction`."""

    ledger: LedgerHealth
    duplicate_credits: list[DuplicateCredit] = Field(serialization_alias="duplicateCredits")
    duplicate_excess_total: Decimal = Field(serialization_alias="duplicateExcessTotal")
    provider_drift: list[BalanceDrift] = Field(serialization_alias="providerDrift")
    provider_drift_total: Decimal = Field(serialization_alias="providerDriftTotal")
    customer_drift: list[BalanceDrift] = Field(serialization_alias="customerDrift")
    customer_drift_total: Decimal = Field(serialization_alias="customerDriftTotal")
