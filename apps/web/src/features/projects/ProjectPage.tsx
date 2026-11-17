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

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

export function ProjectPage() {
  const { organizationId } = useParams();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [workspaceId, setWorkspaceId] = useState("");
  const [moveTargets, setMoveTargets] = useState<Record<string, string>>({});

  if (!organizationId) return <p role="alert">Organization context is missing.</p>;

  const workspaces = useQuery({
    queryKey: ["workspaces", organizationId],
    queryFn: () => listWorkspaces(apiClient, organizationId)
  });
  const projects = useQuery({
    queryKey: ["projects", organizationId],
    queryFn: () => listProjects(apiClient, organizationId)
  });

  const refreshProjects = async () => {
    await queryClient.invalidateQueries({ queryKey: ["projects", organizationId] });
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
    }
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
    onSuccess: refreshProjects
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;
    create.mutate();
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
            {workspaces.data?.map((workspace) => (
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
        {projects.data?.map((project) => {
          const moveTarget = moveTargets[project.id] ?? project.workspace_id ?? "";
          return (
            <li key={project.id} data-testid={"project-" + project.id}>
              <strong>{project.name}</strong> — {project.status} — workspace{" "}
              {project.workspace_id ?? "none"}
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
                    {workspaces.data?.map((workspace) => (
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