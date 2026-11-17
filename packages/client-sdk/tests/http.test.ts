import { describe, expect, it } from "vitest";

import { ApiClient } from "../src/http";

describe("ApiClient security transport", () => {
  it("sends cookies and CSRF on unsafe requests", async () => {
    const calls: RequestInit[] = [];
    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1",
      fetchImpl: (async (_input: RequestInfo | URL, init?: RequestInit) => {
        calls.push(init ?? {});
        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "content-type": "application/json" }
        });
      }) as typeof fetch
    });
    client.setCsrfToken("csrf-token");

    await client.request("/organizations", {
      method: "POST",
      body: JSON.stringify({ name: "Org" })
    });

    expect(calls[0]?.credentials).toBe("include");
    const headers = new Headers(calls[0]?.headers);
    expect(headers.get("x-openvietgis-csrf")).toBe("csrf-token");
    expect(headers.get("content-type")).toBe("application/json");
  });

  it("does not add CSRF to safe requests", async () => {
    const calls: RequestInit[] = [];
    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1",
      fetchImpl: (async (_input: RequestInfo | URL, init?: RequestInit) => {
        calls.push(init ?? {});
        return new Response(JSON.stringify({ ok: true }), { status: 200 });
      }) as typeof fetch
    });
    client.setCsrfToken("csrf-token");

    await client.request("/me");

    expect(new Headers(calls[0]?.headers).has("x-openvietgis-csrf")).toBe(false);
  });
});
