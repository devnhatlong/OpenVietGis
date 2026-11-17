import { describe, expect, it } from "vitest";

import {
  ApiClient,
  createProject,
  createWorkspace,
  listProjects,
  listWorkspaces,
  updateProject
} from "../src";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("workspace and project client", () => {
  it("uses organization-scoped collection paths", async () => {
    const paths: string[] = [];
    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1",
      fetchImpl: (async (input: RequestInfo | URL) => {
        paths.push(new URL(String(input)).pathname);
        return json([]);
      }) as typeof fetch
    });

    await listWorkspaces(client, "org-a");
    await listProjects(client, "org-a");

    expect(paths).toEqual([
      "/api/v1/organizations/org-a/workspaces",
      "/api/v1/organizations/org-a/projects"
    ]);
  });

  it("preserves omitted-vs-null workspace move semantics", async () => {
    const bodies: unknown[] = [];
    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1",
      fetchImpl: (async (_input: RequestInfo | URL, init?: RequestInit) => {
        bodies.push(init?.body ? JSON.parse(String(init.body)) : undefined);
        return json(
          {
            id: "p1",
            organization_id: "o1",
            workspace_id: null,
            name: "Project",
            slug: "project",
            status: "active"
          },
          200
        );
      }) as typeof fetch
    });

    client.setCsrfToken("csrf");
    await createWorkspace(client, "o1", { name: "W", slug: "w" });
    await createProject(client, "o1", {
      name: "Project",
      slug: "project",
      workspace_id: "w1"
    });
    await updateProject(client, "o1", "p1", { name: "Renamed" });
    await updateProject(client, "o1", "p1", { workspace_id: null });

    expect(bodies[2]).toEqual({ name: "Renamed" });
    expect(bodies[3]).toEqual({ workspace_id: null });
  });
});
