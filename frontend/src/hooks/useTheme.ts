import { useCallback, useEffect, useState } from "react";

type Theme = "light" | "dark";
const KEY = "ledgerly-theme";

/** Light-first is the identity; dark is a peer. Seeded from the OS preference
 *  on first boot, then the user's explicit choice wins and persists. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    const stored = localStorage.getItem(KEY);
    if (stored === "light" || stored === "dark") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem(KEY, theme);
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  return { theme, toggle };
}
