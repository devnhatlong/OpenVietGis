import {
  createProject,
  listProjects,
  listWorkspaces,
  loadCsrfToken,
  updateProject
} from "@openvietgis/client-sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiClient } from "../../app/api";
import { currentProtectedData, protectedQueryOptions } from "../../app/protected-query";
import { FreshAccount } from "../auth/FreshAccount";

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function OrganizationProjects({ organizationId, userId }: { organizationId: string; userId: string }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [workspaceId, setWorkspaceId] = useState("");
  const [moveTargets, setMoveTargets] = useState<Record<string, string>>({});

  const workspaces = useQuery({
    queryKey: ["workspaces", organizationId, userId],
    queryFn: () => listWorkspaces(apiClient, organizationId),
    ...protectedQueryOptions
  });
  const projects = useQuery({
    queryKey: ["projects", organizationId, userId],
    queryFn: () => listProjects(apiClient, organizationId),
    ...protectedQueryOptions
  });

  const refreshProjects = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["projects", organizationId, userId] }),
      queryClient.invalidateQueries({ queryKey: ["workspaces", organizationId, userId] })
    ]);
  };

  const create = useMutation({
    mutationFn: async () => {
      await loadCsrfToken(apiClient);
      return createProject(apiClient, organizationId, {
        name: name.trim(),
        slug: slugify(slug || name),
        ...(workspaceId ? { workspace_id: workspaceId } : {})
      });
    },
    onSuccess: async () => {
      setName("");
      setSlug("");
      setWorkspaceId("");
      await refreshProjects();
    },
    onError: refreshProjects
  });

  const update = useMutation({
    mutationFn: async ({
      projectId,
      input
    }: {
      projectId: string;
      input: {
        workspace_id?: string | null;
        status?: "active" | "archived" | "deleted";
      };
    }) => {
      await loadCsrfToken(apiClient);
      return updateProject(apiClient, organizationId, projectId, input);
    },
    onSuccess: refreshProjects,
    onError: refreshProjects
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;
    create.mutate();
  }

  const visibleProjects = currentProtectedData(projects);
  const visibleWorkspaces = currentProtectedData(workspaces);
  if (!visibleProjects || !visibleWorkspaces) {
    const checking = !projects.error && !workspaces.error &&
      (projects.isPending || projects.fetchStatus !== "idle" ||
        workspaces.isPending || workspaces.fetchStatus !== "idle");
    return (
      <main>
        <Link to="/">← Organizations</Link>
        <h1>Projects</h1>
        {checking ? <p>Checking project access…</p> : <p role="alert">Unable to load project access.</p>}
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 960, margin: "40px auto", fontFamily: "system-ui, sans-serif" }}>
      <p>
        <Link to={"/organizations/" + organizationId}>← Organization</Link>{" "}
        <Link to={"/organizations/" + organizationId + "/workspaces"}>Workspaces</Link>
      </p>
      <h1>Projects</h1>

      <form onSubmit={submit}>
        <label>
          Project name
          <input
            aria-label="Project name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              if (!slug) setSlug(slugify(event.target.value));
            }}
            required
          />
        </label>
        <label>
          Project slug
          <input
            aria-label="Project slug"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            required
          />
        </label>
        <label>
          Project workspace
          <select
            aria-label="Project workspace"
            value={workspaceId}
            onChange={(event) => setWorkspaceId(event.target.value)}
          >
            <option value="">Ungrouped</option>
            {visibleWorkspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={create.isPending}>
          Create project
        </button>
      </form>

      {create.error ? <p role="alert">Unable to create project.</p> : null}
      {update.error ? <p role="alert">Unable to update project.</p> : null}

      <ul data-testid="project-list">
        {visibleProjects.map((project) => {
          const moveTarget = moveTargets[project.id] ?? project.workspace_id ?? "";
          return (
            <li key={project.id} data-testid={"project-" + project.id}>
              <strong>{project.name}</strong> — {project.status} — workspace{" "}
              {project.workspace_id ?? "none"}{" "}
              {project.status !== "deleted" ? (
                <Link to={"/organizations/" + encodeURIComponent(organizationId) + "/projects/" + encodeURIComponent(project.id) + "/spatial"}>Spatial catalog</Link>
              ) : null}
              <div>
                <label>
                  Workspace for {project.name}
                  <select
                    aria-label={"Workspace for " + project.name}
                    value={moveTarget}
                    onChange={(event) =>
                      setMoveTargets((current) => ({
                        ...current,
                        [project.id]: event.target.value
                      }))
                    }
                  >
                    <option value="">Ungrouped</option>
                    {visibleWorkspaces.map((workspace) => (
                      <option key={workspace.id} value={workspace.id}>
                        {workspace.name}
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  onClick={() =>
                    update.mutate({
                      projectId: project.id,
                      input: {
                        workspace_id: moveTarget || null
                      }
                    })
                  }
                >
                  Move {project.name}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    update.mutate({
                      projectId: project.id,
                      input: { workspace_id: null }
                    })
                  }
                >
                  Ungroup {project.name}
                </button>
                {project.status === "active" ? (
                  <button
                    type="button"
                    onClick={() =>
                      update.mutate({
                        projectId: project.id,
                        input: { status: "archived" }
                      })
                    }
                  >
                    Archive {project.name}
                  </button>
                ) : project.status === "archived" ? (
                  <button
                    type="button"
                    onClick={() =>
                      update.mutate({
                        projectId: project.id,
                        input: { status: "active" }
                      })
                    }
                  >
                    Restore {project.name}
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </main>
  );
}

export function ProjectPage() {
  const { organizationId } = useParams();
  if (!organizationId) return <p role="alert">Organization context is missing.</p>;
  return (
    <FreshAccount key={organizationId}>
      {(account) => (
        <OrganizationProjects
          key={organizationId + ":" + account.id}
          organizationId={organizationId}
          userId={account.id}
        />
      )}
    </FreshAccount>
  );
}
