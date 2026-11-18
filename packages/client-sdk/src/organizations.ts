import type { components, operations } from "./generated/tenant-core";
import { ApiClient } from "./http";

export type OrganizationRole = "owner" | "admin" | "member" | "guest";
export type OrganizationStatus = "active" | "suspended" | "deleted";

export interface MyOrganization {
  id: string;
  name: string;
  slug: string;
  role: OrganizationRole;
  status?: OrganizationStatus;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  status: OrganizationStatus;
}

export interface OrganizationMembership {
  id: string;
  organization_id: string;
  user_id: string;
  role: OrganizationRole;
  status: "active" | "suspended" | "revoked";
}

export interface OrganizationCreateResult {
  organization: Organization;
  owner_membership: OrganizationMembership;
}

export type ResourceGrant = components["schemas"]["ResourceGrant"];
export type ResourceGrantCreate = components["schemas"]["ResourceGrantCreate"];
export type MembershipUpdate = operations["updateOrganizationMembership"]["requestBody"]["content"]["application/json"];
export type OrganizationUpdate = operations["updateOrganization"]["requestBody"]["content"]["application/json"];
export type EffectivePermissionsScope = NonNullable<operations["getEffectivePermissions"]["parameters"]["query"]>;
export type EffectivePermissions = operations["getEffectivePermissions"]["responses"][200]["content"]["application/json"];

function organizationPath(organizationId: string): string {
  return "/organizations/" + encodeURIComponent(organizationId);
}

export function getOrganization(client: ApiClient, organizationId: string): Promise<Organization> {
  return client.request<Organization>(organizationPath(organizationId));
}

export function updateOrganization(client: ApiClient, organizationId: string, input: OrganizationUpdate): Promise<Organization> {
  return client.request<Organization>(organizationPath(organizationId), { method: "PATCH", body: JSON.stringify(input) });
}

export function listOrganizationMembers(client: ApiClient, organizationId: string): Promise<OrganizationMembership[]> {
  return client.request<OrganizationMembership[]>(organizationPath(organizationId) + "/members");
}

export function updateOrganizationMembership(client: ApiClient, organizationId: string, membershipId: string, input: MembershipUpdate): Promise<void> {
  return client.requestWithoutBody(organizationPath(organizationId) + "/members/" + encodeURIComponent(membershipId), { method: "PATCH", body: JSON.stringify(input) });
}

export function transferOrganizationOwnership(client: ApiClient, organizationId: string, targetMembershipId: string): Promise<void> {
  return client.requestWithoutBody(organizationPath(organizationId) + "/ownership-transfer", { method: "POST", body: JSON.stringify({ target_membership_id: targetMembershipId }) });
}

export function listResourceGrants(client: ApiClient, organizationId: string): Promise<ResourceGrant[]> {
  return client.request<ResourceGrant[]>(organizationPath(organizationId) + "/grants");
}

export function createResourceGrant(client: ApiClient, organizationId: string, input: ResourceGrantCreate): Promise<void> {
  return client.requestWithoutBody(organizationPath(organizationId) + "/grants", { method: "POST", body: JSON.stringify(input) });
}

export function revokeResourceGrant(client: ApiClient, organizationId: string, grantId: string): Promise<void> {
  return client.requestWithoutBody(organizationPath(organizationId) + "/grants/" + encodeURIComponent(grantId) + "/revoke", { method: "POST" });
}

export function getEffectivePermissions(client: ApiClient, organizationId: string, scope: EffectivePermissionsScope = {}): Promise<EffectivePermissions> {
  const query = new URLSearchParams();
  if (scope.workspace_id) query.set("workspace_id", scope.workspace_id);
  if (scope.project_id) query.set("project_id", scope.project_id);
  const suffix = query.size ? "?" + query.toString() : "";
  return client.request<EffectivePermissions>(organizationPath(organizationId) + "/effective-permissions" + suffix);
}

export function listMyOrganizations(client: ApiClient): Promise<MyOrganization[]> {
  return client.request<MyOrganization[]>("/me/organizations");
}

export function createOrganization(
  client: ApiClient,
  input: { name: string; slug: string }
): Promise<OrganizationCreateResult> {
  return client.request<OrganizationCreateResult>("/organizations", {
    method: "POST",
    body: JSON.stringify(input)
  });
}
