import { ApiError, getCurrentUser, type CurrentUser } from "@openvietgis/client-sdk";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { apiClient } from "../../app/api";
import { currentProtectedData, protectedQueryOptions } from "../../app/protected-query";
import { LoginPanel } from "./LoginPanel";

export function FreshAccount({ children }: { children: (account: CurrentUser) => ReactNode }) {
  const user = useQuery({
    queryKey: ["me"],
    queryFn: () => getCurrentUser(apiClient),
    ...protectedQueryOptions
  });

  if (user.fetchStatus !== "idle" || user.isPending) {
    return <p>Checking your account…</p>;
  }
  if (user.error instanceof ApiError && user.error.status === 401) return <LoginPanel />;

  const account = currentProtectedData(user);
  if (!account || account.status !== "active") {
    return <p role="alert">Unable to load your account.</p>;
  }
  return children(account);
}
