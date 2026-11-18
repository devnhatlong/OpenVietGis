import { describe, expect, it } from "vitest";

import {
  ApiClient,
  ApiError,
  SpatialApiError,
  getSpatialSource,
  listSpatialSources,
  registerSpatialSource,
  retireSpatialSource,
  updateSpatialSource
} from "../src";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("spatial source SDK", () => {
  it("always encodes both scope IDs and the source ID and preserves the cursor", async () => {
    const urls: string[] = [];
    const client = new ApiClient({
      baseUrl: "https://example.test/api/v1",
      fetchImpl: (async (input) => {
        urls.push(String(input));
        return json({ organization_id: "org", project_id: "project", items: [], next_after_id: null });
      }) as typeof fetch
    });
    await listSpatialSources(client, "org /", "project?", { limit: 2, after_id: "item+" });
    await getSpatialSource(client, "org /", "project?", "source/#");
    expect(urls).toEqual([
      "https://example.test/api/v1/organizations/org%20%2F/projects/project%3F/spatial/sources?limit=2&after_id=item%2B",
      "https://example.test/api/v1/organizations/org%20%2F/projects/project%3F/spatial/sources/source%2F%23"
    ]);
  });

  it("uses exact mutation shape and existing CSRF transport", async () => {
    const requests: { path: string; method: string | undefined; body: unknown; csrf: string | null }[] = [];
    const client = new ApiClient({
      baseUrl: "https://example.test/api/v1",
      fetchImpl: (async (input, init) => {
        requests.push({
          path: new URL(String(input)).pathname,
          method: init?.method,
          body: JSON.parse(String(init?.body)),
          csrf: new Headers(init?.headers).get("x-openvietgis-csrf")
        });
        return json({ resource_id: "source" }, 201);
      }) as typeof fetch
    });
    client.setCsrfToken("csrf-token");
    await registerSpatialSource(client, "o", "p", { reference_key: "reference_empty_4326", name: "Source" });
    await updateSpatialSource(client, "o", "p", "s", {
      expected_revision: 1,
      declared_crs: { authority: "EPSG", code: 4326, coordinate_order: "xy" }
    });
    await retireSpatialSource(client, "o", "p", "s", { expected_revision: 2 });
    expect(requests).toEqual([
      {
        path: "/api/v1/organizations/o/projects/p/spatial/sources", method: "POST",
        body: { reference_key: "reference_empty_4326", name: "Source" }, csrf: "csrf-token"
      },
      {
        path: "/api/v1/organizations/o/projects/p/spatial/sources/s", method: "PATCH",
        body: { expected_revision: 1, declared_crs: { authority: "EPSG", code: 4326, coordinate_order: "xy" } },
        csrf: "csrf-token"
      },
      {
        path: "/api/v1/organizations/o/projects/p/spatial/sources/s/retire", method: "POST",
        body: { expected_revision: 2 }, csrf: "csrf-token"
      }
    ]);
  });

  it("preserves typed spatial conflicts without swallowing R002 authorization errors", async () => {
    const client = new ApiClient({
      baseUrl: "https://example.test/api/v1",
      fetchImpl: (async (_input, init) => init?.method === "PATCH"
        ? json({ code: "STALE_CATALOG_REVISION", detail: "stale" }, 409)
        : json({ detail: "denied" }, 403)) as typeof fetch
    });
    const failure = await updateSpatialSource(client, "o", "p", "s", {
      expected_revision: 1, name: "Renamed"
    }).catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(SpatialApiError);
    expect(failure).toMatchObject({ status: 409, code: "STALE_CATALOG_REVISION" });
    if (failure instanceof ApiError) expect(await failure.response.json()).toEqual({
      code: "STALE_CATALOG_REVISION", detail: "stale"
    });
    const denied = await getSpatialSource(client, "o", "p", "s").catch((error: unknown) => error);
    expect(denied).toBeInstanceOf(ApiError);
    expect(denied).not.toBeInstanceOf(SpatialApiError);
    expect(denied).toMatchObject({ status: 403 });
  });
});
