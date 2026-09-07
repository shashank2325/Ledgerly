import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useTheme } from "@/hooks/useTheme";
import { useAuth } from "@/hooks/useAuth";

/** Top-level destinations (DESIGN.md §4). Reports sits between Ledger and
 *  Accounts: it is a *view over* the ledger, so it belongs next to it, and
 *  above Accounts, which is reference data rather than analysis. */
const NAV = [
  { to: "/app", label: "Overview", end: true },
  { to: "/app/ledger", label: "Ledger" },
  { to: "/app/reports", label: "Reports" },
  { to: "/app/accounts", label: "Accounts" },
  { to: "/app/settings", label: "Settings" },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <ul className="flex flex-col gap-0.5">
      {NAV.map((item) => (
        <li key={item.to}>
          <NavLink
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              // 44px min height on touch: below that, taps land on neighbours.
              `flex items-center min-h-11 md:min-h-0 md:py-1.5 t-body transition-colors ${
                isActive ? "text-ink font-medium" : "text-ink-muted hover:text-ink"
              }`
            }
          >
            {({ isActive }) => (
              <span className="flex items-center gap-2">
                <span
                  className={`w-[2px] h-3.5 ${isActive ? "bg-accent" : "bg-transparent"}`}
                  aria-hidden="true"
                />
                {item.label}
              </span>
            )}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

function Account({ stacked = false }: { stacked?: boolean }) {
  const { theme, toggle } = useTheme();
  const { username, logout } = useAuth();
  return (
    <div className={stacked ? "flex flex-col gap-2 items-start" : "flex items-center gap-4"}>
      <button
        onClick={toggle}
        className="t-small text-ink-faint hover:text-ink-muted transition-colors"
        aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
      >
        {theme === "dark" ? "Light" : "Dark"}
      </button>
      <div
        className={`flex items-baseline gap-2 ${
          stacked ? "pt-2 rule-t w-full" : ""
        }`}
      >
        <span className="t-small text-ink-faint truncate">{username ?? "—"}</span>
        <button
          onClick={logout}
          className="t-small text-ink-faint hover:text-ink-muted transition-colors ml-auto"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}

export function AppShell() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  // Close on navigation, so a tap that changes page never leaves the drawer
  // covering the content it just loaded.
  useEffect(() => setOpen(false), [location.pathname]);

  // Escape closes it, and body scroll is locked while it is open — otherwise
  // the page behind scrolls under the drawer on iOS.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <div className="min-h-screen md:h-screen flex flex-col md:flex-row bg-canvas text-ink md:overflow-hidden">
      {/* ── Mobile bar ─────────────────────────────────────────────────────
          Sticky rather than fixed: fixed positioning plus iOS's collapsing
          address bar is where mobile layouts go wrong. */}
      <header className="md:hidden sticky top-0 z-30 bg-canvas rule-b flex items-center
                         justify-between px-4 h-14 shrink-0">
        <div className="t-h1 select-none">
          Ledgerly<span className="text-accent">.</span>
        </div>
        <button
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls="mobile-nav"
          aria-label={open ? "Close menu" : "Open menu"}
          className="w-11 h-11 -mr-2 flex flex-col items-center justify-center gap-[5px]"
        >
          {/* Three rules that become a cross. Same hairline vocabulary as the
              rest of the app rather than an imported icon set. */}
          <span
            className={`block w-5 h-px bg-ink transition-transform duration-200 ${
              open ? "translate-y-[6px] rotate-45" : ""
            }`}
          />
          <span
            className={`block w-5 h-px bg-ink transition-opacity duration-200 ${
              open ? "opacity-0" : ""
            }`}
          />
          <span
            className={`block w-5 h-px bg-ink transition-transform duration-200 ${
              open ? "-translate-y-[6px] -rotate-45" : ""
            }`}
          />
        </button>
      </header>

      {/* ── Mobile drawer ──────────────────────────────────────────────── */}
      {open && (
        <>
          <div
            className="md:hidden fixed inset-0 top-14 z-20 bg-canvas/70 backdrop-blur-sm"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <nav
            id="mobile-nav"
            className="md:hidden fixed inset-x-0 top-14 z-20 bg-canvas rule-b px-4 py-4
                       flex flex-col gap-4"
          >
            <NavItems onNavigate={() => setOpen(false)} />
            <div className="pt-3 rule-t">
              <Account />
            </div>
          </nav>
        </>
      )}

      {/* ── Desktop sidebar ────────────────────────────────────────────────
          Text labels always readable — no icons-only collapse (§3.5). */}
      <nav className="hidden md:flex w-[200px] shrink-0 rule-r h-screen flex-col px-5 py-6">
        <div className="t-h1 mb-8 select-none">
          Ledgerly
          {/* The one flourish: a violet period. Transfers are the thesis and
              violet is their color. */}
          <span className="text-accent">.</span>
        </div>
        <div className="flex-1">
          <NavItems />
        </div>
        <Account stacked />
      </nav>

      {/* Content left-aligned within the pane, not centered — centered content
          in a wide viewport reads as marketing. Padding tightens on small
          screens where 40px of gutter is a meaningful share of the width. */}
      <main className="flex-1 min-w-0 md:h-screen md:overflow-y-auto">
        <div className="max-w-[1100px] px-4 py-6 md:px-10 md:py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
