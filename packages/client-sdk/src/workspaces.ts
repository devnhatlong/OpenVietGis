import { ApiClient } from "./http";

export type WorkspaceStatus = "active" | "archived" | "deleted";

export interface Workspace {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  status: WorkspaceStatus;
}

export function listWorkspaces(client: ApiClient, organizationId: string): Promise<Workspace[]> {
  return client.request<Workspace[]>(
    "/organizations/" + encodeURIComponent(organizationId) + "/workspaces"
  );
}

export function createWorkspace(
  client: ApiClient,
  organizationId: string,
  input: { name: string; slug: string }
): Promise<Workspace> {
  return client.request<Workspace>(
    "/organizations/" + encodeURIComponent(organizationId) + "/workspaces",
    { method: "POST", body: JSON.stringify(input) }
  );
}

export function updateWorkspace(
  client: ApiClient,
  organizationId: string,
  workspaceId: string,
  input: { name?: string; status?: WorkspaceStatus }
): Promise<Workspace> {
  return client.request<Workspace>(
    "/organizations/" +
      encodeURIComponent(organizationId) +
      "/workspaces/" +
      encodeURIComponent(workspaceId),
    { method: "PATCH", body: JSON.stringify(input) }
  );
}
