import { describe, expect, it } from "vitest";

import {
  ApiClient, ApiError, acceptInvitation, createInvitation, createResourceGrant,
  getEffectivePermissions, listOrganizationMembers, listResourceGrants,
  revokeInvitation, revokeResourceGrant, transferOrganizationOwnership,
  updateOrganizationMembership
} from "../src";
import type { InvitationCreate, ResourceGrantCreate } from "../src";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("grants and invitations client contract", () => {
  it("keeps membership and grant operations explicitly organization scoped", async () => {
    const calls: Array<{ url: string; method: string | undefined; body: unknown; csrf: string | null; credentials: RequestCredentials | undefined }> = [];
    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1",
      fetchImpl: (async (input: RequestInfo | URL, init?: RequestInit) => {
        calls.push({
          url: String(input),
          method: init?.method,
          body: init?.body ? JSON.parse(String(init.body)) : undefined,
          csrf: new Headers(init?.headers).get("x-openvietgis-csrf"),
          credentials: init?.credentials
        });
        if (init?.method === "GET") return json([]);
        return new Response(null, { status: init?.method === "PATCH" ? 200 : 204 });
      }) as typeof fetch
    });
    client.setCsrfToken("test-csrf");
    const grant: ResourceGrantCreate = {
      subject_kind: "membership", subject_id: "member-1",
      scope_kind: "project", project_id: "project-1", role: "viewer"
    };

    await listOrganizationMembers(client, "org/A");
    await updateOrganizationMembership(client, "org/A", "member/1", { status: "suspended" });
    await transferOrganizationOwnership(client, "org/A", "member-2");
    await listResourceGrants(client, "org/B");
    await createResourceGrant(client, "org/B", grant);
    await revokeResourceGrant(client, "org/B", "grant/1");

    expect(calls.map((call) => new URL(call.url).pathname)).toEqual([
      "/api/v1/organizations/org%2FA/members",
      "/api/v1/organizations/org%2FA/members/member%2F1",
      "/api/v1/organizations/org%2FA/ownership-transfer",
      "/api/v1/organizations/org%2FB/grants",
      "/api/v1/organizations/org%2FB/grants",
      "/api/v1/organizations/org%2FB/grants/grant%2F1/revoke"
    ]);
    expect(calls.map((call) => call.method)).toEqual(["GET", "PATCH", "POST", "GET", "POST", "POST"]);
    expect(calls[1]?.body).toEqual({ status: "suspended" });
    expect(calls[2]?.body).toEqual({ target_membership_id: "member-2" });
    expect(calls[4]?.body).toEqual(grant);
    expect(calls.filter((call) => call.method !== "GET").every((call) => call.csrf === "test-csrf" && call.credentials === "include")).toBe(true);
    expect(calls[0]?.csrf).toBeNull();
  });

  it("encodes both permission-context IDs and returns server permission codes", async () => {
    const urls: URL[] = [];
    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1",
      fetchImpl: (async (input: RequestInfo | URL) => {
        urls.push(new URL(String(input)));
        return json({ permissions: ["project.read"] });
      }) as typeof fetch
    });
    expect(await getEffectivePermissions(client, "org-b", { workspace_id: "w/1", project_id: "p?2" })).toEqual({ permissions: ["project.read"] });
    expect(urls[0]?.pathname).toBe("/api/v1/organizations/org-b/effective-permissions");
    expect(urls[0]?.searchParams.get("workspace_id")).toBe("w/1");
    expect(urls[0]?.searchParams.get("project_id")).toBe("p?2");
    await getEffectivePermissions(client, "org-b");
    expect(urls[1]?.search).toBe("");
  });

  it("issues once, sends the secret in a POST body only, and uses CSRF", async () => {
    const calls: Array<{ url: string; init: RequestInit | undefined }> = [];
    const secret = "synthetic-invitation-secret-for-test-only";
    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1",
      fetchImpl: (async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        calls.push({ url, init });
        if (url.endsWith("/revoke")) return new Response(null, { status: 204 });
        if (url.endsWith("/accept")) return json({ membership: {
          id: "m1", organization_id: "org-a", user_id: "user-2", role: "member", status: "active"
        }, grant: null });
        return json({ id: "invite-1", organization_id: "org-a", status: "pending", secret }, 201);
      }) as typeof fetch
    });
    client.setCsrfToken("test-csrf");
    const invitation: InvitationCreate = {
      target: { kind: "email", email: "example@example.test" },
      organization_role: "member",
      resource_grant: { scope_kind: "project", project_id: "p1", role: "viewer" },
      expires_at: "2030-01-01T00:00:00Z"
    };
    const issued = await createInvitation(client, "org-a", invitation);
    expect(issued.secret).toBe(secret);
    const body = { organization_id: issued.organization_id, invitation_id: issued.id, secret };
    expect((await acceptInvitation(client, body)).membership.organization_id).toBe("org-a");
    await revokeInvitation(client, "org-a", "invite-1");
    expect(calls.map((call) => new URL(call.url).pathname)).toEqual([
      "/api/v1/organizations/org-a/invitations",
      "/api/v1/invitations/accept",
      "/api/v1/organizations/org-a/invitations/invite-1/revoke"
    ]);
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual(invitation);
    expect(JSON.parse(String(calls[1]?.init?.body))).toEqual(body);
    expect(calls.every((call) => !call.url.includes(secret))).toBe(true);
    expect(calls.every((call) => call.init?.method === "POST" && new Headers(call.init.headers).get("x-openvietgis-csrf") === "test-csrf")).toBe(true);
  });

  it("does not swallow forbidden mutations, even with bodyless response handling", async () => {
    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1",
      fetchImpl: (async () => new Response(null, { status: 403 })) as typeof fetch
    });
    await expect(revokeInvitation(client, "org-a", "invite-1")).rejects.toBeInstanceOf(ApiError);
  });
});
