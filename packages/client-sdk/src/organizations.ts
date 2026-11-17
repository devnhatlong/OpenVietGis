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
