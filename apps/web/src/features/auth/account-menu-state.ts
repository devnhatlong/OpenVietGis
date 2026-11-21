import type { CurrentUser } from "@openvietgis/client-sdk";

export interface AccountMenuState {
  displayName: string;
  email: string | null;
  initials: string;
  checking: boolean;
  networkWarning: boolean;
}

export function buildAccountMenuState(
  account: CurrentUser,
  checking: boolean,
  networkWarning: boolean
): AccountMenuState {
  const initials = account.display_name
    .split(/\s+/)
    .filter(Boolean)
    .slice(-2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return {
    displayName: account.display_name,
    email: account.email_snapshot ?? null,
    initials: initials || "U",
    checking,
    networkWarning
  };
}
