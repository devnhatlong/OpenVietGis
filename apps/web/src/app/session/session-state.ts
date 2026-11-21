import type { CurrentUser } from "@openvietgis/client-sdk";

export type SessionPhase =
  | "unknown"
  | "authenticated"
  | "checking"
  | "signed_out"
  | "unavailable";

export interface SessionShellState {
  phase: SessionPhase;
  account: CurrentUser | null;
  lastConfirmedAt: number | null;
  errorKind: "authorization" | "network" | "account" | null;
}

export type SessionEvent =
  | { type: "check_started" }
  | { type: "check_succeeded"; account: CurrentUser; at: number }
  | { type: "check_unauthorized" }
  | { type: "check_failed" }
  | { type: "logout_confirmed" };

export const initialSessionShellState: SessionShellState = {
  phase: "unknown",
  account: null,
  lastConfirmedAt: null,
  errorKind: null
};

export function reduceSessionShellState(
  state: SessionShellState,
  event: SessionEvent
): SessionShellState {
  switch (event.type) {
    case "check_started":
      return state.account
        ? { ...state, phase: "checking", errorKind: null }
        : { ...state, phase: "unknown", errorKind: null };
    case "check_succeeded":
      return event.account.status === "active"
        ? {
            phase: "authenticated",
            account: event.account,
            lastConfirmedAt: event.at,
            errorKind: null
          }
        : {
            phase: "unavailable",
            account: null,
            lastConfirmedAt: state.lastConfirmedAt,
            errorKind: "account"
          };
    case "check_unauthorized":
    case "logout_confirmed":
      return {
        phase: "signed_out",
        account: null,
        lastConfirmedAt: state.lastConfirmedAt,
        errorKind: "authorization"
      };
    case "check_failed":
      return state.account
        ? { ...state, phase: "authenticated", errorKind: "network" }
        : {
            phase: "unavailable",
            account: null,
            lastConfirmedAt: state.lastConfirmedAt,
            errorKind: "network"
          };
  }
}
