import { describe, expect, it } from "vitest";

import {
  ApiClient, SpatialApiError, createSpatialLayer, getSpatialLayer, listSpatialLayers,
  renameSpatialLayer, retireSpatialLayer
} from "../src";

describe("spatial Layer SDK", () => {
  it("encodes scope, cursor and layer ID; preserves the exact mutation wire shape", async () => {
    const calls: { url: string; method: string; body: unknown; csrf: string | null }[] = [];
    const client = new ApiClient({
      baseUrl: "https://test.invalid/api/v1",
      fetchImpl: (async (input, init) => {
        calls.push({
          url: String(input), method: init?.method ?? "GET",
          body: init?.body ? JSON.parse(String(init.body)) : null,
          csrf: new Headers(init?.headers).get("x-openvietgis-csrf")
        });
        return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
      }) as typeof fetch
    });
    client.setCsrfToken("test-token");
    await listSpatialLayers(client, "o/", "p?", { limit: 2, after_id: "x+" });
    await getSpatialLayer(client, "o/", "p?", "l/#");
    await createSpatialLayer(client, "o/", "p?", { source_id: "source", name: "Layer" });
    await renameSpatialLayer(client, "o/", "p?", "l/#", { expected_revision: 1, name: "New" });
    await retireSpatialLayer(client, "o/", "p?", "l/#", { expected_revision: 2 });
    const base = "https://test.invalid/api/v1/organizations/o%2F/projects/p%3F/layers";
    expect(calls.map(call => [call.url, call.method, call.body])).toEqual([
      [base + "?limit=2&after_id=x%2B", "GET", null],
      [base + "/l%2F%23", "GET", null],
      [base, "POST", { source_id: "source", name: "Layer" }],
      [base + "/l%2F%23", "PATCH", { expected_revision: 1, name: "New" }],
      [base + "/l%2F%23/retire", "POST", { expected_revision: 2 }]
    ]);
    expect(calls.slice(2).every(call => call.csrf === "test-token")).toBe(true);
  });

  it("preserves independent stale layer conflict", async () => {
    const client = new ApiClient({
      baseUrl: "https://test.invalid/api/v1",
      fetchImpl: (async () => new Response(
        JSON.stringify({ code: "STALE_LAYER_REVISION", detail: "stale" }),
        { status: 409, headers: { "content-type": "application/json" } }
      )) as typeof fetch
    });
    const error = await renameSpatialLayer(client, "o", "p", "l", {
      expected_revision: 1, name: "New"
    }).catch((failure: unknown) => failure);
    expect(error).toBeInstanceOf(SpatialApiError);
    expect(error).toMatchObject({ status: 409, code: "STALE_LAYER_REVISION" });
  });
});
