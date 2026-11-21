import { describe, expect, it } from "vitest";

import {
  buildSaveIndicatorView,
  deriveSaveIndicatorState
} from "./save-indicator";

describe("save indicator", () => {
  it.each([
    [{ dirty: false, pendingStatus: null }, "clean"],
    [{ dirty: true, pendingStatus: null }, "dirty"],
    [{ dirty: true, pendingStatus: "saving" }, "saving"],
    [{ dirty: false, pendingStatus: "committed" }, "saved"],
    [{ dirty: true, pendingStatus: "conflict" }, "conflict"],
    [{ dirty: true, pendingStatus: "denied" }, "failed"],
    [{ dirty: true, pendingStatus: "unresolved" }, "unresolved"]
  ] as const)("maps parent outcome %j to %s", (input, expected) => {
    expect(
      deriveSaveIndicatorState({
        dirty: input.dirty,
        pendingStatus: input.pendingStatus
      })
    ).toBe(expected);
  });

  it("only claims saved after an authoritative committed outcome", () => {
    expect(
      buildSaveIndicatorView({
        dirty: true,
        pendingStatus: "saving",
        revision: 4
      }).label
    ).toBe("Đang lưu…");

    expect(
      buildSaveIndicatorView({
        dirty: false,
        pendingStatus: "committed",
        revision: 5
      }).label
    ).toBe("Đã lưu phiên bản bản đồ 5");
  });

  it("keeps conflict and unresolved outcomes honest", () => {
    expect(
      buildSaveIndicatorView({
        dirty: true,
        pendingStatus: "conflict",
        revision: 7
      }).detail
    ).toContain("Tải lại");

    expect(
      buildSaveIndicatorView({
        dirty: true,
        pendingStatus: "unresolved",
        revision: 7
      }).detail
    ).toContain("đối chiếu");
  });
});
