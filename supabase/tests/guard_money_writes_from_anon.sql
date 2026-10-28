-- Verifies 20261027200000_guard_money_writes_from_anon.sql. Everything runs in one transaction and is
-- rolled back, so no data changes. Fails with 'FAIL: ...' if a check does not hold.
-- Requires at least one row in provider, customer, withdrawal_history and wallet_transaction.

begin;

set local role anon;

do $$
declare
  p uuid := (select id from public.provider limit 1);
  c uuid := (select id from public.customer limit 1);
  w uuid := (select id from public.withdrawal_history limit 1);
  t uuid := (select id from public.wallet_transaction limit 1);
begin
  begin
    update public.provider set "walletAmount" = '999999' where id = p;
    raise exception 'FAIL: anon changed provider wallet';
  exception when insufficient_privilege then null;
  end;

  begin
    update public.customer set wallet_amount = 999999 where id = c;
    raise exception 'FAIL: anon changed customer wallet';
  exception when insufficient_privilege then null;
  end;

  begin
    update public.withdrawal_history set "paymentStatus" = "paymentStatus" where id = w;
    raise exception 'FAIL: anon updated withdrawal_history';
  exception when insufficient_privilege then null;
  end;

  begin
    update public.wallet_transaction set note = note where id = t;
    raise exception 'FAIL: anon updated wallet_transaction';
  exception when insufficient_privilege then null;
  end;

  -- Profile edits that leave the wallet unchanged must still work for anon (signup flows).
  update public.customer set wallet_amount = wallet_amount where id = c;
  update public.provider set "walletAmount" = "walletAmount" where id = p;
end $$;

reset role;
set local role authenticated;

do $$
declare
  p uuid := (select id from public.provider limit 1);
  c uuid := (select id from public.customer limit 1);
begin
  -- Released apps still write wallets while signed in; step 1 must not break them.
  update public.provider set "walletAmount" = "walletAmount" where id = p;
  update public.customer set wallet_amount = coalesce(wallet_amount, 0) + 0.01 where id = c;
end $$;

rollback;
