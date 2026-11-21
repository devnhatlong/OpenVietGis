import { describe, expect, it } from "vitest";

import { buildAccountMenuState } from "./account-menu-state";

const account = {
  id: "user-1",
  display_name: "Nguyễn Trọng Triệu",
  email_snapshot: "trieu@example.test",
  status: "active" as const
};

describe("account menu state", () => {
  it("exposes only safe account display fields", () => {
    expect(buildAccountMenuState(account, false, false)).toEqual({
      displayName: "Nguyễn Trọng Triệu",
      email: "trieu@example.test",
      initials: "TT",
      checking: false,
      networkWarning: false
    });
  });

  it("represents ambiguous network revalidation without claiming logout", () => {
    const state = buildAccountMenuState(account, true, true);
    expect(state.checking).toBe(true);
    expect(state.networkWarning).toBe(true);
    expect(state.displayName).toBe("Nguyễn Trọng Triệu");
  });
});
