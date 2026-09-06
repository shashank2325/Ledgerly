import { NavLink, Outlet } from "react-router-dom";
import { useTheme } from "@/hooks/useTheme";

/** Four top-level destinations. Resist adding a fifth (DESIGN.md §4). */
const NAV = [
  { to: "/", label: "Overview", end: true },
  { to: "/ledger", label: "Ledger" },
  { to: "/accounts", label: "Accounts" },
  { to: "/settings", label: "Settings" },
];

export function AppShell() {
  const { theme, toggle } = useTheme();

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

        <button
          onClick={toggle}
          className="t-small text-ink-faint hover:text-ink-muted text-left transition-colors"
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? "Light" : "Dark"}
        </button>
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
