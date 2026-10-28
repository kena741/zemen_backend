-- Plan 4a containment, step 1: callers holding only the public anon key may not move money.
--
-- Today `provider`, `customer`, `withdrawal_history` and `wallet_transaction` accept writes from the
-- `anon` role (RLS `using (true)` plus table grants). Released apps perform these writes while signed
-- in (`authenticated`), so this step leaves them working. Edge Functions and lolelink-admin server
-- routes use `service_role` and are unaffected.
--
-- Signup may still insert `customer` / `provider` rows as anon, as long as the wallet starts at zero.

create or replace function public.guard_money_writes_from_anon()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if current_user <> 'anon' then
    return coalesce(new, old);
  end if;

  if tg_table_name = 'provider' then
    if tg_op = 'INSERT' and coalesce(new."walletAmount", '') ~ '[1-9]' then
      raise exception 'provider wallet cannot be set without signing in' using errcode = '42501';
    elsif tg_op = 'UPDATE' and new."walletAmount" is distinct from old."walletAmount" then
      raise exception 'provider wallet cannot be changed without signing in' using errcode = '42501';
    end if;
  elsif tg_table_name = 'customer' then
    if tg_op = 'INSERT' and coalesce(new.wallet_amount, 0) <> 0 then
      raise exception 'customer wallet cannot be set without signing in' using errcode = '42501';
    elsif tg_op = 'UPDATE' and new.wallet_amount is distinct from old.wallet_amount then
      raise exception 'customer wallet cannot be changed without signing in' using errcode = '42501';
    end if;
  else
    raise exception '% cannot be written without signing in', tg_table_name using errcode = '42501';
  end if;

  return coalesce(new, old);
end;
$$;

drop trigger if exists guard_money_writes_from_anon on public.provider;
create trigger guard_money_writes_from_anon
  before insert or update on public.provider
  for each row execute function public.guard_money_writes_from_anon();

drop trigger if exists guard_money_writes_from_anon on public.customer;
create trigger guard_money_writes_from_anon
  before insert or update on public.customer
  for each row execute function public.guard_money_writes_from_anon();

drop trigger if exists guard_money_writes_from_anon on public.withdrawal_history;
create trigger guard_money_writes_from_anon
  before insert or update or delete on public.withdrawal_history
  for each row execute function public.guard_money_writes_from_anon();

drop trigger if exists guard_money_writes_from_anon on public.wallet_transaction;
create trigger guard_money_writes_from_anon
  before insert or update or delete on public.wallet_transaction
  for each row execute function public.guard_money_writes_from_anon();
