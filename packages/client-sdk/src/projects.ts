import { ApiClient } from "./http";

export type ProjectStatus = "active" | "archived" | "deleted";

export interface Project {
  id: string;
  organization_id: string;
  workspace_id: string | null;
  name: string;
  slug: string;
  status: ProjectStatus;
}

export function listProjects(
  client: ApiClient,
  organizationId: string,
  workspaceId?: string
): Promise<Project[]> {
  const query = workspaceId ? "?workspace_id=" + encodeURIComponent(workspaceId) : "";
  return client.request<Project[]>(
    "/organizations/" + encodeURIComponent(organizationId) + "/projects" + query
  );
}

export function getProject(
  client: ApiClient,
  organizationId: string,
  projectId: string
): Promise<Project> {
  return client.request<Project>(
    "/organizations/" +
      encodeURIComponent(organizationId) +
      "/projects/" +
      encodeURIComponent(projectId)
  );
}

export function createProject(
  client: ApiClient,
  organizationId: string,
  input: { name: string; slug: string; workspace_id?: string | null }
): Promise<Project> {
  return client.request<Project>(
    "/organizations/" + encodeURIComponent(organizationId) + "/projects",
    { method: "POST", body: JSON.stringify(input) }
  );
}

export function updateProject(
  client: ApiClient,
  organizationId: string,
  projectId: string,
  input: {
    name?: string;
    workspace_id?: string | null;
    status?: ProjectStatus;
  }
): Promise<Project> {
  return client.request<Project>(
    "/organizations/" +
      encodeURIComponent(organizationId) +
      "/projects/" +
      encodeURIComponent(projectId),
    { method: "PATCH", body: JSON.stringify(input) }
  );
}
