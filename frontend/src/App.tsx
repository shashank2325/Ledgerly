import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { AuthProvider, useAuth } from "@/hooks/useAuth";
import { Landing } from "@/pages/Landing";
import { Overview } from "@/pages/Overview";
import { Ledger } from "@/pages/Ledger";
import { Reports } from "@/pages/Reports";
import { Accounts } from "@/pages/Accounts";
import { Settings } from "@/pages/Settings";

/**
 * Route guard.
 *
 * This is convenience, NOT security. Every protected endpoint independently
 * verifies the session token server-side, so bypassing this component in the
 * browser yields a shell that can fetch nothing (SPEC §31: never rely on
 * frontend-only authorization).
 */
function RequireAuth() {
  const { token, ready } = useAuth();
  // Blank rather than a redirect while the stored token is being validated —
  // redirecting first would bounce a signed-in user out on every refresh.
  if (!ready) return <div className="min-h-screen bg-canvas" />;
  if (!token) return <Navigate to="/" replace />;
  return <AppShell />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/app" element={<RequireAuth />}>
            <Route index element={<Overview />} />
            <Route path="ledger" element={<Ledger />} />
            <Route path="reports" element={<Reports />} />
            <Route path="accounts" element={<Accounts />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          {/* Unknown paths fall back to the landing page, which itself
              redirects to /app when a session exists. */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
