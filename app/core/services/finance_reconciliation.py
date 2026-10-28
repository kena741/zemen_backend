"""Read-only wallet reconciliation (Plan 4 shadow check). Never writes.

Ledger rule observed on betegna (2026-10-27): a wallet balance equals the sum of
its `wallet_transaction` rows (credits minus debits, withdrawals included as
provider debits). 464/469 provider and 392/399 customer balances satisfy it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_NUM = r"'^\s*-?[0-9]+(\.[0-9]+)?\s*$'"
_SIGNED = 'case when w."isCredit" then w.amount::numeric else -w.amount::numeric end'

_DUPLICATE_CREDITS = text(
    f"""
    select w."transactionId" as transaction_id,
           w.type,
           w.amount,
           w.note,
           count(*) as copies,
           min(w."createdDate") as first_at,
           max(w."createdDate") as last_at,
           (count(*) - 1) * w.amount::numeric as excess_amount
    from wallet_transaction w
    where w."isCredit" is true
      and w."transactionId" is not null
      and w.amount ~ {_NUM}
    group by w."transactionId", w.type, w.amount, w.note
    having count(*) > 1
    order by excess_amount desc, last_at desc
    limit :limit
    """
)

_PROVIDER_DRIFT = text(
    f"""
    with led as (
        select coalesce(w.provider_id, p.id) as pid, sum({_SIGNED}) as net, count(*) as n
        from wallet_transaction w
        left join provider p on p.user_id = w."userId" or p.id = w."userId"
        where w.type = 'provider' and w.amount ~ {_NUM}
        group by 1
    )
    select p.id as account_id,
           nullif(p."walletAmount", '')::numeric as balance,
           coalesce(l.net, 0) as ledger_net,
           nullif(p."walletAmount", '')::numeric - coalesce(l.net, 0) as drift,
           coalesce(l.n, 0) as ledger_rows
    from provider p
    left join led l on l.pid = p.id
    where p."walletAmount" ~ {_NUM}
      and abs(nullif(p."walletAmount", '')::numeric - coalesce(l.net, 0)) >= 0.01
    order by abs(nullif(p."walletAmount", '')::numeric - coalesce(l.net, 0)) desc
    limit :limit
    """
)

_CUSTOMER_DRIFT = text(
    f"""
    with led as (
        select coalesce(w.customer_id, c.id) as cid, sum({_SIGNED}) as net, count(*) as n
        from wallet_transaction w
        left join customer c on c.user_id = w."userId" or c.id = w."userId"
        where w.type = 'customer' and w.amount ~ {_NUM}
        group by 1
    )
    select c.id as account_id,
           coalesce(c.wallet_amount, 0) as balance,
           coalesce(l.net, 0) as ledger_net,
           coalesce(c.wallet_amount, 0) - coalesce(l.net, 0) as drift,
           coalesce(l.n, 0) as ledger_rows
    from customer c
    left join led l on l.cid = c.id
    where abs(coalesce(c.wallet_amount, 0) - coalesce(l.net, 0)) >= 0.01
    order by abs(coalesce(c.wallet_amount, 0) - coalesce(l.net, 0)) desc
    limit :limit
    """
)

_LEDGER_HEALTH = text(
    f"""
    select
      (select count(*) from wallet_transaction) as total_rows,
      (select count(*) from wallet_transaction where amount is null or amount !~ {_NUM}) as non_numeric_amounts,
      (select count(*) from wallet_transaction where type is null) as untyped_rows,
      (select count(*) from wallet_transaction w where w.type = 'customer' and not exists (
          select 1 from customer c where c.id = w.customer_id or c.user_id = w."userId" or c.id = w."userId")) as orphan_customer_rows,
      (select count(*) from wallet_transaction w where w.type = 'provider' and not exists (
          select 1 from provider p where p.id = w.provider_id or p.user_id = w."userId" or p.id = w."userId")) as orphan_provider_rows,
      (select count(*) from provider where "walletAmount" is not null and "walletAmount" !~ {_NUM}) as non_numeric_provider_balances
    """
)


_CENT = Decimal("0.01")
_MONEY_KEYS = ("balance", "ledger_net", "drift", "excess_amount")


def _rows(result) -> list[dict[str, Any]]:
    rows = []
    for r in result:
        row = dict(r._mapping)
        for k in _MONEY_KEYS:
            if row.get(k) is not None:
                row[k] = Decimal(row[k]).quantize(_CENT)
        rows.append(row)
    return rows


def _total(rows: list[dict[str, Any]], key: str) -> Decimal:
    return sum((abs(r[key] or Decimal(0)) for r in rows), Decimal(0)).quantize(_CENT)


async def reconciliation_report(db: AsyncSession, *, limit: int = 100) -> dict[str, Any]:
    duplicates = _rows(await db.execute(_DUPLICATE_CREDITS, {"limit": limit}))
    providers = _rows(await db.execute(_PROVIDER_DRIFT, {"limit": limit}))
    customers = _rows(await db.execute(_CUSTOMER_DRIFT, {"limit": limit}))
    health = dict((await db.execute(_LEDGER_HEALTH)).one()._mapping)
    return {
        "ledger": health,
        "duplicate_credits": duplicates,
        "duplicate_excess_total": _total(duplicates, "excess_amount"),
        "provider_drift": providers,
        "provider_drift_total": _total(providers, "drift"),
        "customer_drift": customers,
        "customer_drift_total": _total(customers, "drift"),
    }
