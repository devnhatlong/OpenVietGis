import { describe, expect, it } from "vitest";

import {
  canReadHistory, createHistoryTraversal, formatHistoryValue, HISTORY_PAGE_SIZE,
  historyKey, historyResponseMatchesScope, nextHistoryPage, previousHistoryPage,
  revisionEntries, type HistoryScope
} from "./catalog-history";

const scope: HistoryScope = {
  accountId: "actor-a", organizationId: "org-a", projectId: "project-a"
};

const project = { id: scope.projectId, organization_id: scope.organizationId, status: "active" };
const item = (id: string) => ({ id, organization_id: scope.organizationId, project_id: scope.projectId });

describe("current-authority spatial history", () => {
  it("isolates account, organization, project and server continuation under the mutation prefix", () => {
    expect(historyKey(scope, null)).toEqual([
      "spatial-catalog", "actor-a", "org-a", "project-a", "changes", HISTORY_PAGE_SIZE, null
    ]);
    for (const key of ["accountId", "organizationId", "projectId"] as const) {
      expect(historyKey({ ...scope, [key]: "changed" }, null)).not.toEqual(historyKey(scope, null));
    }
    expect(historyKey(scope, "change-20")).not.toEqual(historyKey(scope, null));
  });

  it("requires current exact Project metadata, permits archived reads and hides deleted scope", () => {
    expect(canReadHistory(scope, project)).toBe(true);
    expect(canReadHistory(scope, { ...project, status: "archived" })).toBe(true);
    expect(canReadHistory(scope, undefined)).toBe(false);
    expect(canReadHistory(scope, { ...project, status: "deleted" })).toBe(false);
    expect(canReadHistory(scope, { ...project, id: "another-project" })).toBe(false);
    expect(canReadHistory(scope, { ...project, organization_id: "another-org" })).toBe(false);
  });

  it("rejects mismatched outer or item scopes, oversized, unordered and invalid continuation pages", () => {
    const envelope = { organization_id: scope.organizationId, project_id: scope.projectId };
    const page = { ...envelope, items: [item("change-01"), item("change-02")], next_after_id: null };
    expect(historyResponseMatchesScope(scope, page, null)).toBe(true);
    expect(historyResponseMatchesScope(scope, { ...page, items: [] }, null)).toBe(true);
    for (const key of ["organization_id", "project_id"] as const) {
      expect(historyResponseMatchesScope(scope, { ...page, [key]: "other" }, null)).toBe(false);
      expect(historyResponseMatchesScope(scope, {
        ...page, items: [page.items[0]!, { ...page.items[1]!, [key]: "other" }]
      }, null)).toBe(false);
    }
    expect(historyResponseMatchesScope(scope, page, "change-01")).toBe(false);
    expect(historyResponseMatchesScope(scope, { ...page, items: [...page.items].reverse() }, null)).toBe(false);
    expect(historyResponseMatchesScope(scope, { ...page, items: [item("same"), item("same")] }, null)).toBe(false);
    expect(historyResponseMatchesScope(scope, { ...page, next_after_id: "change-02" }, null)).toBe(false);
    const full = Array.from({ length: HISTORY_PAGE_SIZE }, (_, index) => item("change-" + String(index + 1).padStart(3, "0")));
    const valid = { ...envelope, items: full, next_after_id: full.at(-1)!.id };
    expect(historyResponseMatchesScope(scope, valid, null)).toBe(true);
    expect(historyResponseMatchesScope(scope, { ...valid, next_after_id: "foreign-cursor" }, null)).toBe(false);
    expect(historyResponseMatchesScope(scope, { ...valid, items: [...full, item("extra")] }, null)).toBe(false);
  });

  it("moves only via server continuation, returns to the exact previous cursor", () => {
    const first = createHistoryTraversal();
    const second = nextHistoryPage(first, "change-020");
    const third = nextHistoryPage(second, "change-040");
    expect(third).toEqual({ cursor: "change-040", history: [null, "change-020"] });
    expect(previousHistoryPage(third)).toEqual(second);
    expect(previousHistoryPage(second)).toEqual(first);
    expect(previousHistoryPage(first)).toEqual(first);
    expect(nextHistoryPage(third, null)).toEqual(third);
    expect(nextHistoryPage(third, "change-040")).toEqual(third);
    expect(nextHistoryPage(third, "change-020")).toEqual(third);
  });

  it("renders only safe scalars and preserves distinction between null, empty, false, zero and strings", () => {
    expect(formatHistoryValue(null)).toBe("null");
    expect(formatHistoryValue("")).toBe('""');
    expect(formatHistoryValue("0")).toBe('"0"');
    expect(formatHistoryValue(0)).toBe("0");
    expect(formatHistoryValue(false)).toBe("false");
    expect(formatHistoryValue("1234567890.12345678901234567890")).toBe('"1234567890.12345678901234567890"');
    expect(formatHistoryValue("2025-01-01T00:00:00.012345Z")).toBe('"2025-01-01T00:00:00.012345Z"');
    for (const value of [undefined, NaN, Infinity, ["raw feature"], { secret: "do not expose" }]) {
      expect(formatHistoryValue(value)).toBe("Unavailable");
    }
  });

  it("renders only explicit typed revision fields, never generic object contents", () => {
    expect(revisionEntries("layer", { layer_revision: 2 })).toEqual([["Layer revision", 2]]);
    expect(revisionEntries("data_source", {
      catalog_revision: 2, content_revision: "content-token", schema_revision: "schema-token"
    })).toEqual([
      ["Catalog revision", 2], ["Content revision", "content-token"], ["Schema revision", "schema-token"]
    ]);
    expect(revisionEntries("layer", null)).toEqual([]);
    expect(revisionEntries("data_source", { layer_revision: 1 })).toEqual([]);
    expect(revisionEntries("layer", { layer_revision: 2, secret: "not-rendered" })).toEqual([["Layer revision", 2]]);
  });
});
