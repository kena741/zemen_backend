"""Admin Finance, Payouts, Taxes, and Ledger API router."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.admin.requests.finance import (
    ChapaTransferRequest,
    ChapaVerifyTransferRequest,
    ChapaWebhookPayload,
    CompleteWithdrawalRequest,
    CreateCountryTaxRequest,
    FetchProviderPaymentMethodsRequest,
    ReviewWithdrawalRequest,
    UpdateCountryTaxRequest,
    UpsertProviderPaymentMethodRequest,
)
from app.api.v1.schemas.admin.responses.finance import (
    ChapaBalanceResponse,
    CountryTaxListResponse,
    CountryTaxResponseItem,
    EnrichedWalletTransactionResponseItem,
    ProviderPaymentMethodResponseItem,
    ProviderPaymentMethodsResponse,
    ProviderPayoutAnalysisResponse,
    WalletTransactionListResponse,
    WithdrawalListResponse,
    WithdrawalResponseItem,
    WithdrawalSingleResponse,
)
from app.core.security.admin_deps import AdminContext, require_admin_permission
from app.core.services.admin.audit_service import AdminAuditService
from app.core.services.admin.finance_service import FinanceAdminService
from app.persistence.repositories.activity_log_repo import ActivityLogRepository
from app.persistence.repositories.provider_payment_method_repo import ProviderPaymentMethodRepository
from app.persistence.repositories.provider_repo import ProviderRepository
from app.persistence.repositories.tax_repo import CountryTaxRepository
from app.persistence.repositories.wallet_transaction_repo import WalletTransactionRepository
from app.persistence.repositories.withdrawal_repo import WithdrawalRepository
from app.persistence.sqlalchemy.deps import get_db

router = APIRouter(prefix="/admin", tags=["admin-finance"])

Db = Annotated[AsyncSession, Depends(get_db)]
CanReadFinance = Annotated[AdminContext, Depends(require_admin_permission("finance:read"))]
CanWriteFinance = Annotated[AdminContext, Depends(require_admin_permission("finance:write"))]


def _get_finance_service(db: AsyncSession) -> FinanceAdminService:
    withdrawal_repo = WithdrawalRepository(db)
    provider_repo = ProviderRepository(db)
    payment_method_repo = ProviderPaymentMethodRepository(db)
    wallet_repo = WalletTransactionRepository(db)
    tax_repo = CountryTaxRepository(db)
    audit_repo = ActivityLogRepository(db)
    audit_service = AdminAuditService(audit_repo)

    return FinanceAdminService(
        withdrawal_repo=withdrawal_repo,
        provider_repo=provider_repo,
        payment_method_repo=payment_method_repo,
        wallet_repo=wallet_repo,
        tax_repo=tax_repo,
        audit_service=audit_service,
    )


# --- Withdrawals & Payout Requests -------------------------------------------


@router.get(
    "/finance/payouts",
    response_model=WithdrawalListResponse,
    operation_id="admin_finance_list_payouts",
    summary="List provider withdrawal payout requests",
)
@router.get(
    "/payout/requests",
    response_model=WithdrawalListResponse,
    include_in_schema=False,
)
async def list_payouts(
    _: CanReadFinance,
    db: Db,
    statuses: list[str] | None = Query(default=None),
    provider_id: UUID | None = Query(default=None, alias="providerId"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> WithdrawalListResponse:
    service = _get_finance_service(db)
    items = await service.list_withdrawals(
        statuses=statuses,
        provider_id=provider_id,
        offset=offset,
        limit=limit,
    )
    return WithdrawalListResponse(data=[WithdrawalResponseItem.model_validate(w) for w in items])


@router.get(
    "/finance/badge-count",
    operation_id="admin_finance_badge_count",
    summary="Count pending withdrawal requests for sidebar badge",
)
async def get_finance_badge_count(_: CanReadFinance, db: Db) -> dict[str, int]:
    service = _get_finance_service(db)
    count = await service.count_badge()
    return {"count": count}


@router.post(
    "/finance/payouts/review",
    response_model=WithdrawalSingleResponse,
    operation_id="admin_finance_review_payout",
    summary="Approve or reject a provider withdrawal request",
)
@router.post(
    "/payout/review",
    response_model=WithdrawalSingleResponse,
    include_in_schema=False,
)
async def review_payout(
    body: ReviewWithdrawalRequest,
    ctx: CanWriteFinance,
    db: Db,
) -> WithdrawalSingleResponse:
    service = _get_finance_service(db)
    w = await service.review_withdrawal(
        withdrawal_id=body.withdrawal_id,
        action=body.action,
        admin_note=body.admin_note,
        rejection_reason=body.rejection_reason,
        ctx=ctx,
    )
    return WithdrawalSingleResponse(data=WithdrawalResponseItem.model_validate(w))


@router.post(
    "/finance/payouts/complete",
    response_model=WithdrawalSingleResponse,
    operation_id="admin_finance_complete_payout",
    summary="Mark payout complete and deduct provider wallet balance",
)
@router.post(
    "/payout/complete",
    response_model=WithdrawalSingleResponse,
    include_in_schema=False,
)
async def complete_payout(
    body: CompleteWithdrawalRequest,
    ctx: CanWriteFinance,
    db: Db,
) -> WithdrawalSingleResponse:
    service = _get_finance_service(db)
    w = await service.complete_withdrawal(
        withdrawal_id=body.withdrawal_id,
        admin_note=body.admin_note,
        ctx=ctx,
    )
    return WithdrawalSingleResponse(data=WithdrawalResponseItem.model_validate(w))


@router.post(
    "/finance/payouts/chapa-transfer",
    operation_id="admin_finance_chapa_transfer",
    summary="Initiate payout transfer via Chapa Transfer API",
)
@router.post(
    "/payout/chapa-transfer",
    include_in_schema=False,
)
async def chapa_transfer(
    body: ChapaTransferRequest,
    ctx: CanWriteFinance,
    db: Db,
) -> dict[str, Any]:
    service = _get_finance_service(db)
    return await service.chapa_transfer(withdrawal_id=body.withdrawal_id, ctx=ctx)


@router.post(
    "/finance/payouts/chapa-verify-transfer",
    operation_id="admin_finance_chapa_verify_transfer",
    summary="Verify payout transfer status with Chapa and mark complete",
)
@router.post(
    "/payout/chapa-verify-transfer",
    include_in_schema=False,
)
async def chapa_verify_transfer(
    body: ChapaVerifyTransferRequest,
    ctx: CanWriteFinance,
    db: Db,
) -> dict[str, Any]:
    service = _get_finance_service(db)
    return await service.verify_chapa_transfer(withdrawal_id=body.withdrawal_id, ctx=ctx)


@router.post(
    "/finance/payouts/chapa-webhook",
    operation_id="admin_finance_chapa_webhook",
    summary="Webhook receiver for Chapa transfer status events",
)
@router.post(
    "/payout/chapa-webhook",
    include_in_schema=False,
)
async def chapa_webhook(
    body: ChapaWebhookPayload,
    db: Db,
) -> dict[str, Any]:
    service = _get_finance_service(db)
    return await service.handle_chapa_webhook(payload=body.model_dump())


# --- Provider Payment Methods & Wallet Analysis -------------------------------


@router.get(
    "/finance/provider-wallet-analysis",
    response_model=ProviderPayoutAnalysisResponse,
    operation_id="admin_finance_provider_wallet_analysis",
    summary="Calculate comprehensive wallet and payout statistics for a provider",
)
@router.get(
    "/payout/provider-wallet-analysis",
    response_model=ProviderPayoutAnalysisResponse,
    include_in_schema=False,
)
async def provider_wallet_analysis(
    _: CanReadFinance,
    db: Db,
    provider_id: UUID = Query(alias="providerId"),
) -> ProviderPayoutAnalysisResponse:
    service = _get_finance_service(db)
    analysis = await service.analyze_provider_wallet(provider_id=provider_id)
    return ProviderPayoutAnalysisResponse.model_validate(analysis)


@router.get(
    "/finance/export-audit",
    operation_id="admin_finance_export_audit",
    summary="Export payout request history as CSV",
)
@router.get(
    "/payout/export-audit",
    include_in_schema=False,
)
async def export_audit(
    _: CanReadFinance,
    db: Db,
) -> Response:
    service = _get_finance_service(db)
    csv_data = await service.export_audit_csv()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="payout_audit.csv"'},
    )


@router.post(
    "/finance/provider-payment-methods",
    response_model=ProviderPaymentMethodsResponse,
    operation_id="admin_finance_provider_payment_methods",
    summary="Fetch bank payment methods for a list of providers",
)
@router.post(
    "/payout/provider-payment-methods",
    response_model=ProviderPaymentMethodsResponse,
    include_in_schema=False,
)
async def get_provider_payment_methods(
    body: FetchProviderPaymentMethodsRequest,
    _: CanReadFinance,
    db: Db,
) -> ProviderPaymentMethodsResponse:
    service = _get_finance_service(db)
    methods = await service.get_provider_payment_methods(body.provider_ids)
    data = {
        k: ProviderPaymentMethodResponseItem.model_validate(v) if v else None
        for k, v in methods.items()
    }
    return ProviderPaymentMethodsResponse(data=data)


@router.post(
    "/finance/provider-payment-methods-upsert",
    response_model=ProviderPaymentMethodResponseItem,
    operation_id="admin_finance_upsert_provider_payment_method",
    summary="Upsert default bank payment method for provider",
)
@router.post(
    "/payout/provider-payment-methods-upsert",
    response_model=ProviderPaymentMethodResponseItem,
    include_in_schema=False,
)
async def upsert_provider_payment_method(
    body: UpsertProviderPaymentMethodRequest,
    ctx: CanWriteFinance,
    db: Db,
) -> ProviderPaymentMethodResponseItem:
    service = _get_finance_service(db)
    method = await service.upsert_provider_payment_method(
        provider_id=body.provider_id,
        bank_name=body.bank_name,
        account_number=body.account_number,
        holder_name=body.holder_name,
        swift_code=body.swift_code,
        branch_city=body.branch_city,
        branch_country=body.branch_country,
        is_default=body.is_default,
        method_code=body.method_code,
        method_name=body.method_name,
        ctx=ctx,
    )
    return ProviderPaymentMethodResponseItem.model_validate(method)


# --- Ledger & Taxes ----------------------------------------------------------


@router.get(
    "/finance/wallet-transactions",
    response_model=WalletTransactionListResponse,
    operation_id="admin_finance_wallet_transactions",
    summary="List enriched platform wallet transactions",
)
@router.get(
    "/wallet-transactions",
    response_model=WalletTransactionListResponse,
    include_in_schema=False,
)
async def list_wallet_transactions(
    _: CanReadFinance,
    db: Db,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> WalletTransactionListResponse:
    service = _get_finance_service(db)
    txs = await service.list_wallet_transactions(offset=offset, limit=limit)
    return WalletTransactionListResponse(
        data=[EnrichedWalletTransactionResponseItem.model_validate(tx) for tx in txs]
    )


@router.get(
    "/finance/taxes",
    response_model=CountryTaxListResponse,
    operation_id="admin_finance_list_taxes",
    summary="List country tax configurations",
)
async def list_taxes(_: CanReadFinance, db: Db) -> CountryTaxListResponse:
    service = _get_finance_service(db)
    taxes = await service.list_taxes()
    return CountryTaxListResponse(data=[CountryTaxResponseItem.model_validate(t) for t in taxes])


@router.post(
    "/finance/taxes",
    response_model=CountryTaxResponseItem,
    status_code=status.HTTP_201_CREATED,
    operation_id="admin_finance_create_tax",
    summary="Create a new country tax configuration",
)
async def create_tax(
    body: CreateCountryTaxRequest,
    ctx: CanWriteFinance,
    db: Db,
) -> CountryTaxResponseItem:
    service = _get_finance_service(db)
    created = await service.create_tax(
        name=body.name,
        country=body.country,
        value=body.value,
        tax_type=body.type,
        is_fix=body.is_fix,
        active=body.active,
        ctx=ctx,
    )
    return CountryTaxResponseItem.model_validate(created)


@router.patch(
    "/finance/taxes/{tax_id}",
    response_model=CountryTaxResponseItem,
    operation_id="admin_finance_update_tax",
    summary="Update country tax configuration",
)
async def update_tax(
    tax_id: int,
    body: UpdateCountryTaxRequest,
    ctx: CanWriteFinance,
    db: Db,
) -> CountryTaxResponseItem:
    service = _get_finance_service(db)
    updated = await service.update_tax(
        tax_id=tax_id,
        updates=body.model_dump(exclude_unset=True),
        ctx=ctx,
    )
    return CountryTaxResponseItem.model_validate(updated)


@router.delete(
    "/finance/taxes/{tax_id}",
    status_code=status.HTTP_200_OK,
    operation_id="admin_finance_delete_tax",
    summary="Delete country tax configuration",
)
async def delete_tax(
    tax_id: int,
    ctx: CanWriteFinance,
    db: Db,
) -> dict[str, bool]:
    service = _get_finance_service(db)
    await service.delete_tax(tax_id=tax_id, ctx=ctx)
    return {"ok": True}


@router.get(
    "/finance/chapa-balance",
    response_model=ChapaBalanceResponse,
    operation_id="admin_finance_chapa_balance",
    summary="Check current Chapa account balance",
)
@router.get(
    "/chapa/balance",
    response_model=ChapaBalanceResponse,
    include_in_schema=False,
)
async def get_chapa_balance(_: CanReadFinance, db: Db) -> ChapaBalanceResponse:
    service = _get_finance_service(db)
    bal = await service.get_chapa_balance()
    return ChapaBalanceResponse.model_validate(bal)
