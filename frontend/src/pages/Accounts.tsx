import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/layout/PageHeader";
import { Money } from "@/components/ui/Money";
import { Section } from "@/components/ui/primitives";
import { api } from "@/api/client";
import { useApi } from "@/hooks/useApi";
import { ConnectButton } from "@/components/plaid/ConnectButton";
import { RemoveConnection } from "@/components/accounts/RemoveConnection";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/primitives";
import { relativeTime } from "@/utils/date";
import type { Account } from "@/types";

/** Assets and liabilities are subtotaled separately, then netted.
 *  Liability status comes from account TYPE, never from the sign of the
 *  balance — a card with $1,500 owed reports a positive number. */
function AccountRow({ account, onClick }: { account: Account; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left row-hover px-1 rule-b py-2.5 md:py-0 md:h-10
                 grid grid-cols-[minmax(0,1fr)_auto] gap-x-3 gap-y-0.5
                 md:flex md:items-center md:gap-4"
    >
      <span className="md:flex-1 min-w-0 flex items-baseline gap-2">
        <span className="t-body truncate">{account.name}</span>
        <span className="t-num-sm text-ink-faint shrink-0">··{account.mask}</span>
      </span>
      {/* Balance stays on the first line on mobile — it is the reason you
          opened the page. */}
      <span className="text-right md:w-28 md:shrink-0 md:order-none order-1">
        <Money amount={account.current_balance ?? "0"} />
      </span>
      {/* Type and sync age share the second line on mobile. */}
      <span className="order-2 md:order-none col-span-2 md:col-span-1 flex items-baseline
                       gap-2 md:contents">
        <span className="t-small text-ink-muted md:w-28 md:shrink-0 truncate capitalize">
          {account.account_subtype}
        </span>
        <span className="t-small text-ink-faint md:w-24 md:shrink-0 ml-auto md:ml-0">
          {account.last_synced_at ? relativeTime(account.last_synced_at) : "never"}
        </span>
      </span>
    </button>
  );
}

export function Accounts() {
  const navigate = useNavigate();
  const { data, loading, error, refetch } = useApi(() => api.getAccounts());

  if (loading) {
    return (
      <>
        <PageHeader title="Accounts" />
        <SkeletonRows count={8} />
      </>
    );
  }

  if (error) {
    return (
      <>
        <PageHeader title="Accounts" />
        <ErrorState reason={error.message} onRetry={refetch} />
      </>
    );
  }

  const accounts = data?.accounts ?? [];
  const assets = accounts.filter((a) => !a.is_liability);
  const liabilities = accounts.filter((a) => a.is_liability);

  // Totals for display only. Net worth itself comes from the server, which owns
  // the is_liability sign logic (SPEC §3 — no financial logic in the frontend).
  const sum = (list: Account[]) =>
    list.reduce((t, a) => t + Number(a.current_balance ?? 0), 0);
  const assetTotal = sum(assets);
  const liabilityTotal = sum(liabilities);

  const byInstitution = (list: Account[]) =>
    Object.entries(
      list.reduce<Record<string, Account[]>>((acc, a) => {
        const key = a.institution_name ?? "Other";
        (acc[key] ??= []).push(a);
        return acc;
      }, {}),
    );

  return (
    <>
      <PageHeader
        title="Accounts"
        meta={`${accounts.length} connected`}
        action={<ConnectButton onConnected={refetch} />}
      />

      {accounts.length === 0 && (
        <EmptyState message="No accounts connected yet. Connect a bank to get started." />
      )}

      {assets.length > 0 && (
      <Section title="Assets">
        {byInstitution(assets).map(([institution, list]) => (
          <div key={institution} className="mb-5 last:mb-0">
            <div className="flex items-baseline justify-between mb-1 gap-4 flex-wrap">
              <span className="t-small text-ink-faint">{institution}</span>
              {list[0]?.item_id && (
                <RemoveConnection
                  itemId={list[0].item_id}
                  institutionName={institution}
                  accountCount={
                    accounts.filter((a) => a.item_id === list[0]!.item_id).length
                  }
                  onRemoved={refetch}
                />
              )}
            </div>
            {list.map((a) => (
              <AccountRow key={a.account_id} account={a}
                onClick={() => navigate(`/app/ledger?account=${a.account_id}`)} />
            ))}
          </div>
        ))}
        <div className="flex justify-between items-baseline pt-3 rule-t">
          <span className="t-label">Total assets</span>
          <Money amount={assetTotal.toFixed(2)} />
        </div>
      </Section>
      )}

      {liabilities.length > 0 && (
      <Section title="Liabilities">
        {byInstitution(liabilities).map(([institution, list]) => (
          <div key={institution} className="mb-5 last:mb-0">
            <div className="flex items-baseline justify-between mb-1 gap-4 flex-wrap">
              <span className="t-small text-ink-faint">{institution}</span>
              {list[0]?.item_id && (
                <RemoveConnection
                  itemId={list[0].item_id}
                  institutionName={institution}
                  accountCount={
                    accounts.filter((a) => a.item_id === list[0]!.item_id).length
                  }
                  onRemoved={refetch}
                />
              )}
            </div>
            {list.map((a) => (
              <AccountRow key={a.account_id} account={a}
                onClick={() => navigate(`/app/ledger?account=${a.account_id}`)} />
            ))}
          </div>
        ))}
        <div className="flex justify-between items-baseline pt-3 rule-t">
          <span className="t-label">Total liabilities</span>
          <Money amount={liabilityTotal.toFixed(2)} />
        </div>
      </Section>
      )}

      {accounts.length > 0 && (
        <Section>
          <div className="flex justify-between items-baseline">
            <span className="t-h2">Net worth</span>
            {/* Straight from the server — assets minus liabilities, computed
                where the financial logic lives. */}
            <Money amount={data?.net_worth ?? "0"} size="lg" />
          </div>
        </Section>
      )}
    </>
  );
}
