import { describe, expect, it } from "vitest";

import {
  initialSessionShellState,
  reduceSessionShellState
} from "./session-state";

const account = {
  id: "user-1",
  display_name: "Nguyễn Văn A",
  email_snapshot: "a@example.com",
  status: "active" as const
};

describe("session shell state", () => {
  it("keeps a confirmed account while a background check runs", () => {
    const confirmed = reduceSessionShellState(initialSessionShellState, {
      type: "check_succeeded",
      account,
      at: 100
    });

    expect(reduceSessionShellState(confirmed, { type: "check_started" })).toEqual({
      ...confirmed,
      phase: "checking",
      errorKind: null
    });
  });

  it("clears the account on confirmed authorization loss", () => {
    const confirmed = reduceSessionShellState(initialSessionShellState, {
      type: "check_succeeded",
      account,
      at: 100
    });

    const signedOut = reduceSessionShellState(confirmed, {
      type: "check_unauthorized"
    });

    expect(signedOut.phase).toBe("signed_out");
    expect(signedOut.account).toBeNull();
  });

  it("keeps chrome identity after a transient revalidation failure", () => {
    const confirmed = reduceSessionShellState(initialSessionShellState, {
      type: "check_succeeded",
      account,
      at: 100
    });

    const state = reduceSessionShellState(confirmed, { type: "check_failed" });
    expect(state.phase).toBe("authenticated");
    expect(state.account).toEqual(account);
    expect(state.errorKind).toBe("network");
  });
});
