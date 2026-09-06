import { NavLink, Outlet } from "react-router-dom";
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

export function AppShell() {
  const { theme, toggle } = useTheme();
  const { username, logout } = useAuth();

  return (
    <div className="min-h-screen flex bg-canvas text-ink">
      {/* Fixed 200px sidebar, hairline right border. Text labels always
          readable — no icons-only collapse (DESIGN.md §3.5). */}
      <nav className="w-[200px] shrink-0 rule-r min-h-screen sticky top-0 flex flex-col px-5 py-6">
        <div className="t-h1 mb-8 select-none">
          Ledgerly
          {/* The one flourish: a violet period. Transfers are the thesis and
              violet is their color. */}
          <span className="text-accent">.</span>
        </div>

        <ul className="flex flex-col gap-0.5 flex-1">
          {NAV.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `block py-1.5 t-body transition-colors ${
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

        <div className="flex flex-col gap-2 items-start">
          <button
            onClick={toggle}
            className="t-small text-ink-faint hover:text-ink-muted transition-colors"
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          >
            {theme === "dark" ? "Light" : "Dark"}
          </button>
          <div className="flex items-baseline gap-2 pt-2 rule-t w-full">
            <span className="t-small text-ink-faint truncate">{username ?? "—"}</span>
            <button
              onClick={logout}
              className="t-small text-ink-faint hover:text-ink-muted transition-colors ml-auto"
            >
              Sign out
            </button>
          </div>
        </div>
      </nav>

      {/* Content left-aligned within the pane, not centered — centered content
          in a wide viewport reads as marketing. */}
      <main className="flex-1 min-w-0">
        <div className="max-w-[1100px] px-10 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
