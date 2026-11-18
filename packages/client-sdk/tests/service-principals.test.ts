import { describe, expect, it } from "vitest";

import {
  ApiClient,
  createServicePrincipal,
  issueServiceCredential,
  listServicePrincipals,
  revokeServiceCredential,
  revokeServicePrincipal
} from "../src";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("service principal client contract", () => {
  it("keeps management tenant scoped and returns a credential secret once", async () => {
    const calls: Array<{
      path: string;
      method: string | undefined;
      body: unknown;
      csrf: string | null;
    }> = [];
    const secret = "ovgsvc00000000000000000000000000000000_fixture-secret";
    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1",
      fetchImpl: (async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = new URL(String(input)).pathname;
        calls.push({
          path,
          method: init?.method,
          body: init?.body ? JSON.parse(String(init.body)) : undefined,
          csrf: new Headers(init?.headers).get("x-openvietgis-csrf")
        });
        if (init?.method === "GET") return json([]);
        if (path.endsWith("/credentials")) {
          return json({
            id: "credential-1",
            prefix: "ovgsvc000000000",
            secret,
            permission_ceiling: ["project.read"],
            expires_at: null
          }, 201);
        }
        if (path.endsWith("/service-principals")) {
          return json({
            id: "principal-1",
            organization_id: "org/a",
            name: "automation",
            description: null,
            status: "active"
          }, 201);
        }
        return new Response(null, { status: 204 });
      }) as typeof fetch
    });
    client.setCsrfToken("csrf");

    await listServicePrincipals(client, "org/a");
    await createServicePrincipal(client, "org/a", { name: "automation" });
    const issued = await issueServiceCredential(
      client,
      "org/a",
      "principal/1",
      { name: "ci", permission_ceiling: ["project.read"], expires_at: null }
    );
    await revokeServiceCredential(client, "org/a", "principal/1", "cred/1");
    await revokeServicePrincipal(client, "org/a", "principal/1");

    expect(issued.secret).toBe(secret);
    expect(calls.map((call) => call.path)).toEqual([
      "/api/v1/organizations/org%2Fa/service-principals",
      "/api/v1/organizations/org%2Fa/service-principals",
      "/api/v1/organizations/org%2Fa/service-principals/principal%2F1/credentials",
      "/api/v1/organizations/org%2Fa/service-principals/principal%2F1/credentials/cred%2F1/revoke",
      "/api/v1/organizations/org%2Fa/service-principals/principal%2F1/revoke"
    ]);
    expect(calls[2]?.body).toEqual({
      name: "ci",
      permission_ceiling: ["project.read"],
      expires_at: null
    });
    expect(calls.every((call) => !call.path.includes(secret))).toBe(true);
    expect(
      calls
        .filter((call) => call.method !== "GET")
        .every((call) => call.csrf === "csrf")
    ).toBe(true);
  });
});
