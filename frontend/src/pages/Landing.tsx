import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { LoginForm } from "@/components/auth/LoginForm";
import { useTheme } from "@/hooks/useTheme";

/**
 * Landing page.
 *
 * The hero is not a stock illustration — it is the product's actual
 * differentiator rendered live: a matched transfer pair whose two legs visibly
 * cancel. Every competitor stores a transfer as a label on one transaction,
 * which is why they double-count credit-card payments. Showing the pair IS the
 * pitch, and it is the same component the ledger uses.
 */
export function Landing() {
  const { token, ready } = useAuth();
  const { theme, toggle } = useTheme();
  const [showLogin, setShowLogin] = useState(false);

  // Wait for the stored-token check before deciding, otherwise a returning user
  // sees the landing page flash before being redirected.
  if (!ready) return <div className="min-h-screen bg-canvas" />;
  if (token) return <Navigate to="/app" replace />;

  return (
    <div className="min-h-screen bg-canvas text-ink flex flex-col">
      <header className="flex items-center justify-between px-4 sm:px-8 py-5 sm:py-6 max-w-[1100px] w-full mx-auto">
        <div className="t-h1 select-none">
          Ledgerly<span className="text-accent">.</span>
        </div>
        <div className="flex items-center gap-6">
          <button
            onClick={toggle}
            className="t-small text-ink-faint hover:text-ink-muted transition-colors"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
          <button
            onClick={() => setShowLogin(true)}
            className="t-body text-accent hover:underline underline-offset-4"
          >
            Sign in
          </button>
        </div>
      </header>

      <main className="flex-1 max-w-[1100px] w-full mx-auto px-4 sm:px-8 pt-10 sm:pt-16 pb-16 sm:pb-24">
        <h1 className="text-[clamp(2.5rem,7vw,4.5rem)] font-semibold leading-[1.05] tracking-[-0.03em] max-w-3xl">
          Your financial data,
          <br />
          <span className="text-ink-muted">as a data asset.</span>
        </h1>

        <p className="mt-8 t-body text-ink-muted max-w-xl leading-relaxed">
          Most budgeting apps show you records they own. Ledgerly keeps a raw,
          immutable ledger you own — every number traceable to the transactions
          that produced it, and rebuildable from source whenever the rules change.
        </p>

        {/* ── The differentiator, shown rather than claimed ─────────────── */}
        <section className="mt-14 sm:mt-20 rule-t pt-8 sm:pt-10">
          <div className="t-label mb-6">Why the numbers are right</div>

          <div className="grid md:grid-cols-[1.1fr_1fr] gap-8 md:gap-12 items-start">
            <div>
              <h2 className="t-h1 mb-4 max-w-md leading-tight">
                A transfer is two transactions, not a label on one.
              </h2>
              <p className="t-body text-ink-muted leading-relaxed max-w-md">
                Move $2,000 from checking to savings and most apps count it twice —
                once as spending, once as income. They tag a single transaction and
                hope. Ledgerly matches both legs and proves they cancel.
              </p>
              <p className="mt-4 t-small text-ink-faint max-w-md">
                The same logic keeps a credit-card payment from being counted as
                spending. The expense already happened at purchase.
              </p>
            </div>

            {/* Live render of a matched pair — same visual language as the ledger */}
            <div className="border-l-2 border-l-transfer pl-3">
              <div className="rule-b py-2 flex items-baseline justify-between gap-4">
                <span className="flex items-baseline gap-2 min-w-0">
                  <span className="t-body text-transfer">Transfer</span>
                  <span className="t-small text-ink-muted truncate">
                    Checking <span className="text-transfer mx-1">→</span> Savings
                  </span>
                </span>
                <span className="t-num text-transfer whitespace-nowrap">
                  <span aria-hidden="true">→</span>
                  <span className="num-unit">$</span>2,000
                  <span className="num-unit">.00</span>
                </span>
              </div>

              <div className="bg-transfer/[0.04]">
                {[
                  { role: "From", account: "Total Checking ··4821", amount: "−", value: "2,000" },
                  { role: "To", account: "Online Savings ··9013", amount: "+", value: "2,000" },
                ].map((leg) => (
                  <div
                    key={leg.role}
                    className="flex items-baseline justify-between gap-4 py-2 px-2"
                  >
                    <span className="flex items-baseline gap-2 min-w-0">
                      <span className="t-label">{leg.role}</span>
                      <span className="t-small text-ink-faint truncate">{leg.account}</span>
                    </span>
                    <span className="t-num-sm whitespace-nowrap">
                      <span aria-hidden="true">{leg.amount}</span>
                      <span className="num-unit">$</span>
                      {leg.value}
                      <span className="num-unit">.00</span>
                    </span>
                  </div>
                ))}
              </div>

              <div className="flex items-baseline justify-between gap-4 py-2 px-2 rule-t">
                <span className="t-small text-ink-faint">Net effect on spending</span>
                <span className="t-num-sm text-ink-faint">
                  <span className="num-unit">$</span>0<span className="num-unit">.00</span>
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* ── What it is, plainly ───────────────────────────────────────── */}
        <section className="mt-14 sm:mt-20 rule-t pt-8 sm:pt-10">
          <div className="t-label mb-8">Built on</div>
          <div className="grid sm:grid-cols-3 gap-8 sm:gap-10">
            {[
              {
                title: "An immutable raw layer",
                body: "Every payload from your bank is kept exactly as received. Change a rule and five years of history can be rebuilt from source.",
              },
              {
                title: "Queryable history",
                body: "Transactions live in Apache Iceberg on S3 and are queried with Athena — your data in an open table format, not a vendor's database.",
              },
              {
                title: "Serverless and yours",
                body: "Runs entirely in your own AWS account for a few dollars a month. No one else holds the ledger.",
              },
            ].map((item) => (
              <div key={item.title}>
                <h3 className="t-h2 mb-2">{item.title}</h3>
                <p className="t-small text-ink-muted leading-relaxed">{item.body}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="mt-14 sm:mt-20 rule-t pt-8 sm:pt-10 flex items-baseline gap-6 flex-wrap">
          <button
            onClick={() => setShowLogin(true)}
            className="t-body text-accent hover:underline underline-offset-4"
          >
            Sign in to your ledger →
          </button>
          <span className="t-small text-ink-faint">Private. Single user.</span>
        </div>
      </main>

      {showLogin && <LoginForm onClose={() => setShowLogin(false)} />}
    </div>
  );
}
