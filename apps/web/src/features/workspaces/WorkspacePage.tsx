import {
  createWorkspace,
  listWorkspaces,
  loadCsrfToken,
  updateWorkspace
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

export function WorkspacePage() {
  const { organizationId } = useParams();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  if (!organizationId) return <p role="alert">Organization context is missing.</p>;

  const workspaces = useQuery({
    queryKey: ["workspaces", organizationId],
    queryFn: () => listWorkspaces(apiClient, organizationId)
  });

  const create = useMutation({
    mutationFn: async () => {
      await loadCsrfToken(apiClient);
      return createWorkspace(apiClient, organizationId, {
        name: name.trim(),
        slug: slugify(slug || name)
      });
    },
    onSuccess: async () => {
      setName("");
      setSlug("");
      await queryClient.invalidateQueries({ queryKey: ["workspaces", organizationId] });
    }
  });

  const changeStatus = useMutation({
    mutationFn: async ({
      workspaceId,
      status
    }: {
      workspaceId: string;
      status: "active" | "archived" | "deleted";
    }) => {
      await loadCsrfToken(apiClient);
      return updateWorkspace(apiClient, organizationId, workspaceId, { status });
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["workspaces", organizationId] });
    }
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;
    create.mutate();
  }

  return (
    <main style={{ maxWidth: 880, margin: "40px auto", fontFamily: "system-ui, sans-serif" }}>
      <p>
        <Link to={"/organizations/" + organizationId}>← Organization</Link>{" "}
        <Link to={"/organizations/" + organizationId + "/projects"}>Projects</Link>
      </p>
      <h1>Workspaces</h1>

      <form onSubmit={submit}>
        <label>
          Workspace name
          <input
            aria-label="Workspace name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              if (!slug) setSlug(slugify(event.target.value));
            }}
            required
          />
        </label>
        <label>
          Workspace slug
          <input
            aria-label="Workspace slug"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            required
          />
        </label>
        <button type="submit" disabled={create.isPending}>
          Create workspace
        </button>
      </form>

      {create.error ? <p role="alert">Unable to create workspace.</p> : null}
      {changeStatus.error ? <p role="alert">Unable to change workspace status.</p> : null}

      <ul data-testid="workspace-list">
        {workspaces.data?.map((workspace) => (
          <li key={workspace.id} data-testid={"workspace-" + workspace.id}>
            <strong>{workspace.name}</strong> — {workspace.status}{" "}
            {workspace.status === "active" ? (
              <button
                type="button"
                onClick={() =>
                  changeStatus.mutate({
                    workspaceId: workspace.id,
                    status: "archived"
                  })
                }
              >
                Archive {workspace.name}
              </button>
            ) : workspace.status === "archived" ? (
              <button
                type="button"
                onClick={() =>
                  changeStatus.mutate({
                    workspaceId: workspace.id,
                    status: "active"
                  })
                }
              >
                Restore {workspace.name}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() =>
                changeStatus.mutate({
                  workspaceId: workspace.id,
                  status: "deleted"
                })
              }
            >
              Delete {workspace.name}
            </button>
          </li>
        ))}
      </ul>
    </main>
  );
}
