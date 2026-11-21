import { LoginPage } from "./LoginPage";

/**
 * Compatibility wrapper for older feature components.
 * Canonical authentication entry is /login.
 */
export function LoginPanel() {
  return <LoginPage />;
}
