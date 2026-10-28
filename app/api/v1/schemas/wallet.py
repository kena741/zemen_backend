from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.api.v1.schemas.common import APIModel


class WalletTransactionOut(APIModel):
    id: UUID
    amount: str | None = None
    created_date: datetime | None = Field(default=None, serialization_alias="createdDate")
    is_credit: bool | None = Field(default=None, serialization_alias="isCredit")
    note: str | None = None
    payment_type: str | None = Field(default=None, serialization_alias="paymentType")
    transaction_id: str | None = Field(default=None, serialization_alias="transactionId")
    type: str | None = None
    user_id: UUID | None = Field(default=None, serialization_alias="userId")
    provider_id: UUID | None = None
    customer_id: UUID | None = None


class WithdrawalOut(APIModel):
    id: UUID
    amount: str | None = None
    created_date: datetime | None = Field(default=None, serialization_alias="createdDate")
    note: str | None = None
    payment_status: str | None = Field(default=None, serialization_alias="paymentStatus")
    provider_id: UUID | None = Field(default=None, serialization_alias="providerId")
    holder_name: str | None = Field(default=None, serialization_alias="holderName")
    bank_name: str | None = Field(default=None, serialization_alias="bankName")
    account_number: str | None = Field(default=None, serialization_alias="accountNumber")
    rejection_reason: str | None = Field(default=None, serialization_alias="rejectionReason")
