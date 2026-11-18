import { describe, expect, it } from "vitest";

import { ApiClient, createProject, getProject, getReadiness } from "../src";

describe("tenant foundation client", () => {
  it("checks readiness and creates and reads a real tenant record using explicit IDs", async () => {
    const calls: Array<{ path: string; method: string | undefined; body: unknown }> = [];
    const project = {
      id: "project/1", organization_id: "org/1", workspace_id: null,
      name: "client-check", slug: "client-check", status: "active"
    };
    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1/",
      fetchImpl: (async (input: RequestInfo | URL, init?: RequestInit) => {
        const path = new URL(String(input)).pathname;
        calls.push({
          path, method: init?.method,
          body: init?.body ? JSON.parse(String(init.body)) : undefined
        });
        return new Response(JSON.stringify(
          path.endsWith("/health/ready") ? {status: "ready", database: "ready"} : project
        ), {
          status: init?.method === "POST" ? 201 : 200,
          headers: {"content-type": "application/json"}
        });
      }) as typeof fetch
    });
    expect(await getReadiness(client)).toEqual({status: "ready", database: "ready"});
    expect(await createProject(client, "org/1", {
      name: "client-check", slug: "client-check"
    })).toEqual(project);
    expect(await getProject(client, "org/1", "project/1")).toEqual(project);
    expect(calls.map((call) => call.path)).toEqual([
      "/api/v1/health/ready",
      "/api/v1/organizations/org%2F1/projects",
      "/api/v1/organizations/org%2F1/projects/project%2F1"
    ]);
    expect(calls[1]?.method).toBe("POST");
  });
});
