import { describe, expect, expectTypeOf, it } from "vitest";

import { ApiClient, ApiError, SpatialApiError, listSpatialCatalogChanges } from "../src";
import type { SpatialCatalogChange, SpatialCatalogComponents, SpatialChangeList } from "../src";

const base = "https://test.invalid/api/v1";
const change: SpatialCatalogChange = {
  id: "change-id",
  organization_id: "org",
  project_id: "project",
  resource_type: "layer",
  resource_id: "layer-id",
  actor_type: "service_principal",
  actor_id: "actor-id",
  actor_display_snapshot: "Automation",
  operation: "retire_layer",
  created_at: "2026-11-18T12:00:00Z",
  audit_event_id: "audit-id",
  prior_revision: { layer_revision: 1 },
  new_revision: { layer_revision: 2 },
  changes: [{ field: "lifecycle", old_value: "active", new_value: "retired" }]
};
const page: SpatialChangeList = {
  organization_id: "org", project_id: "project", items: [change], next_after_id: change.id
};

describe("scoped catalog change history SDK", () => {
  it("exports the generated wire types and preserves retired resource evidence", async () => {
    expectTypeOf<SpatialCatalogChange>().toEqualTypeOf<
      SpatialCatalogComponents["schemas"]["CatalogChange"]
    >();
    expectTypeOf<SpatialChangeList>().toEqualTypeOf<SpatialCatalogComponents["schemas"]["ChangeList"]>();
    expectTypeOf<ReturnType<typeof listSpatialCatalogChanges>>().toEqualTypeOf<Promise<SpatialChangeList>>();
    const client = new ApiClient({
      baseUrl: base,
      fetchImpl: (async () => Response.json(page)) as typeof fetch
    });
    const actual = await listSpatialCatalogChanges(client, "org", "project");
    expect(actual).toEqual(page);
    expect(actual.items[0]).not.toHaveProperty("source_id");
    expect(actual.items[0]).not.toHaveProperty("layer_id");
    expect(actual.items[0]?.changes).toEqual(change.changes);
  });

  it("encodes the project scope and only sends explicitly supplied pagination", async () => {
    const calls: { url: string; method: string; body: unknown; csrf: string | null }[] = [];
    const client = new ApiClient({
      baseUrl: base,
      fetchImpl: (async (input, init) => {
        calls.push({
          url: String(input), method: init?.method ?? "GET", body: init?.body ?? null,
          csrf: new Headers(init?.headers).get("x-openvietgis-csrf")
        });
        return Response.json(page);
      }) as typeof fetch
    });
    client.setCsrfToken("not-for-reads");
    await listSpatialCatalogChanges(client, "o/", "p?");
    await listSpatialCatalogChanges(client, "o/", "p?", {});
    await listSpatialCatalogChanges(client, "o/", "p?", { limit: 100 });
    await listSpatialCatalogChanges(client, "o/", "p?", { after_id: "cursor +?" });
    await listSpatialCatalogChanges(client, "o/", "p?", { limit: 1, after_id: "cursor +?" });
    const path = base + "/organizations/o%2F/projects/p%3F/spatial/changes";
    expect(calls.map(call => call.url)).toEqual([
      path, path, path + "?limit=100", path + "?after_id=cursor+%2B%3F",
      path + "?limit=1&after_id=cursor+%2B%3F"
    ]);
    expect(calls.every(call => call.method === "GET" && call.body === null && call.csrf === null))
      .toBe(true);
  });

  it.each([401, 403, 404, 422])("keeps authorization and request-validation failures generic (%s)", async status => {
    let count = 0;
    let url = "";
    const privateInput = "private-input";
    const client = new ApiClient({
      baseUrl: base,
      fetchImpl: (async input => {
        count++;
        url = String(input);
        return Response.json({
          detail: status === 422
            ? [{ loc: [], msg: "invalid request payload", type: "value_error" }]
            : "denied"
        }, { status });
      }) as typeof fetch
    });
    const failure = await listSpatialCatalogChanges(client, "org", "project", {
      limit: 101, after_id: privateInput
    }).catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).not.toBeInstanceOf(SpatialApiError);
    expect(failure).toMatchObject({ status });
    expect(String(failure)).not.toContain(privateInput);
    expect(count).toBe(1);
    // The server owns validation: the SDK must not silently clamp limit >100 or retry.
    expect(url).toBe(base + "/organizations/org/projects/project/spatial/changes?limit=101&after_id=private-input");
  });

  it("preserves a recognized fail-closed spatial error code without retry", async () => {
    let count = 0;
    const client = new ApiClient({
      baseUrl: base,
      fetchImpl: (async () => {
        count++;
        return Response.json({ detail: "failure", code: "INVALID_CURSOR" }, { status: 422 });
      }) as typeof fetch
    });
    const failure = await listSpatialCatalogChanges(client, "org", "project", { after_id: "bad" })
      .catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(SpatialApiError);
    expect(failure).toMatchObject({ status: 422, code: "INVALID_CURSOR" });
    expect(count).toBe(1);
  });
});
