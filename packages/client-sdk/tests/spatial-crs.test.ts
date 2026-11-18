import { describe, expect, it } from "vitest";
import { ApiClient, ApiError, listSpatialCrsProfiles, readSpatialFeatures } from "../src";

describe("scoped CRS discovery", () => {
  it("encodes the Project scope and preserves definition-only profiles and operation evidence", async () => {
    const body = { organization_id: "o", project_id: "p", profiles: [{ code: 3405, disposition: "definition_only" }], transformations: [{ operation_id: "exact", evidence_id: "published" }] };
    const urls: string[] = [];
    const client = new ApiClient({ baseUrl: "https://example.test/api/v1", fetchImpl: (async input => {
      urls.push(String(input)); return new Response(JSON.stringify(body), { status: 200 });
    }) as typeof fetch });
    expect(await listSpatialCrsProfiles(client, "org /", "project?")).toEqual(body);
    expect(urls).toEqual(["https://example.test/api/v1/organizations/org%20%2F/projects/project%3F/spatial/crs-profiles"]);
  });
  it("keeps discovery current permission errors typed", async () => {
    const client = new ApiClient({ baseUrl: "https://example.test/api/v1", fetchImpl: (async () => new Response('{"detail":"denied"}', { status: 403 })) as typeof fetch });
    await expect(listSpatialCrsProfiles(client, "o", "p")).rejects.toBeInstanceOf(ApiError);
  });
  it("sends only the explicitly selected response CRS with the original revision pins", async () => {
    let url = "";
    const client = new ApiClient({ baseUrl: "https://example.test/api/v1", fetchImpl: (async input => {
      url = String(input); return new Response('{}', { status: 200 });
    }) as typeof fetch });
    await readSpatialFeatures(client, "o", "p", "l", { content_revision: "old-content", schema_revision: "exact-schema", response_crs: 3857, limit: 20 });
    const query = new URL(url).searchParams;
    expect(Object.fromEntries(query)).toEqual({ content_revision: "old-content", schema_revision: "exact-schema", response_crs: "3857", limit: "20" });
  });
});
