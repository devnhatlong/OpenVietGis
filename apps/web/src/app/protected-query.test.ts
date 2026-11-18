import { describe, expect, it } from "vitest";

import { currentProtectedData, protectedQueryOptions } from "./protected-query";

describe("protected query visibility", () => {
  const completed = {
    data: [{ id: "tenant-private" }],
    error: null,
    fetchStatus: "idle" as const,
    isSuccess: true
  };

  it("renders only a successful, settled read", () => {
    expect(currentProtectedData(completed)).toEqual(completed.data);
    expect(currentProtectedData({ ...completed, data: [] })).toEqual([]);
  });

  it.each(["fetching", "paused"] as const)("does not render cached data while %s", (fetchStatus) => {
    expect(currentProtectedData({ ...completed, fetchStatus })).toBeUndefined();
  });

  it.each([401, 403, 404])("does not render an older successful payload after %s", (status) => {
    expect(currentProtectedData({
      ...completed,
      error: { status },
      isSuccess: false
    })).toBeUndefined();
  });

  it("fails closed even if a result unexpectedly has both an error and success", () => {
    expect(currentProtectedData({ ...completed, error: new Error("denied") })).toBeUndefined();
  });

  it("always revalidates protected data on remount, focus and reconnect", () => {
    expect(protectedQueryOptions).toEqual({
      staleTime: 0,
      refetchOnMount: "always",
      refetchOnWindowFocus: "always",
      refetchOnReconnect: "always"
    });
  });
});
