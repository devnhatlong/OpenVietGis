import { describe, expect, it } from "vitest";

import { ApiClient, getBootstrapStatus, initializeInstallation } from "../src";

describe("bootstrap client contract", () => {
  it("sends authority only in the explicit initialization header with CSRF", async () => {
    const requests: Array<{ path: string; headers: Headers; body: string; method: string | undefined }> = [];
    const authority = "synthetic-bootstrap-authority";
    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1",
      fetchImpl: (async (input: RequestInfo | URL, init?: RequestInit) => {
        requests.push({
          path: new URL(String(input)).pathname,
          headers: new Headers(init?.headers),
          body: String(init?.body ?? ""),
          method: init?.method
        });
        return new Response(JSON.stringify(init?.method === "POST"
          ? { organization_id: "org", owner_membership_id: "owner" }
          : { initialized: false }), {
          status: init?.method === "POST" ? 201 : 200,
          headers: { "content-type": "application/json" }
        });
      }) as typeof fetch
    });
    client.setCsrfToken("synthetic-csrf");
    expect(await getBootstrapStatus(client)).toEqual({ initialized: false });
    expect(await initializeInstallation(client, {
      organization_name: "First organization", organization_slug: "first-org"
    }, authority)).toEqual({ organization_id: "org", owner_membership_id: "owner" });
    expect(requests[0]?.headers.has("Authorization")).toBe(false);
    expect(requests[1]?.headers.get("Authorization") === "Bearer " + authority).toBe(true);
    expect(requests[1]?.headers.get("X-OpenVietGIS-CSRF")).toBe("synthetic-csrf");
    expect(requests[1]?.path).toBe("/api/v1/bootstrap/initialize");
    expect(requests[1]?.body.includes(authority)).toBe(false);
    await getBootstrapStatus(client);
    expect(requests[2]?.headers.has("Authorization")).toBe(false);
  });
});
