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
import { currentProtectedData, protectedQueryOptions } from "../../app/protected-query";
import { FreshAccount } from "../auth/FreshAccount";

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function OrganizationWorkspaces({ organizationId, userId }: { organizationId: string; userId: string }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  const workspaces = useQuery({
    queryKey: ["workspaces", organizationId, userId],
    queryFn: () => listWorkspaces(apiClient, organizationId),
    ...protectedQueryOptions
  });

  async function refreshWorkspaces() {
    await queryClient.invalidateQueries({ queryKey: ["workspaces", organizationId, userId] });
  }

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
      await refreshWorkspaces();
    },
    onError: refreshWorkspaces
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
      await refreshWorkspaces();
    },
    onError: refreshWorkspaces
  });

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;
    create.mutate();
  }

  const visibleWorkspaces = currentProtectedData(workspaces);
  if (!visibleWorkspaces) {
    const checking = !workspaces.error && (workspaces.isPending || workspaces.fetchStatus !== "idle");
    return (
      <main>
        <Link to="/">← Organizations</Link>
        <h1>Không gian làm việc</h1>
        {checking ? <p>Checking workspace access…</p> : <p role="alert">Unable to load workspace access.</p>}
      </main>
    );
  }

  return (
    <main style={{ maxWidth: 880, margin: "40px auto", fontFamily: "system-ui, sans-serif" }}>
      <p>
        <Link to={"/organizations/" + organizationId}>← Organization</Link>{" "}
        <Link to={"/organizations/" + organizationId + "/projects"}>Dự án</Link>
      </p>
      <h1>Không gian làm việc</h1>

      <form onSubmit={submit}>
        <label>
          Tên không gian làm việc
          <input
            aria-label="Tên không gian làm việc"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              if (!slug) setSlug(slugify(event.target.value));
            }}
            required
          />
        </label>
        <label>
          Mã định danh
          <input
            aria-label="Mã định danh"
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            required
          />
        </label>
        <button type="submit" disabled={create.isPending}>
          Tạo không gian làm việc
        </button>
      </form>

      {create.error ? <p role="alert">Unable to create workspace.</p> : null}
      {changeStatus.error ? <p role="alert">Unable to change workspace status.</p> : null}

      <ul data-testid="workspace-list">
        {visibleWorkspaces.map((workspace) => (
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


export function WorkspacePage() {
  const { organizationId } = useParams();
  if (!organizationId) return <p role="alert">Organization context is missing.</p>;
  return (
    <FreshAccount key={organizationId}>
      {(account) => (
        <OrganizationWorkspaces
          key={organizationId + ":" + account.id}
          organizationId={organizationId}
          userId={account.id}
        />
      )}
    </FreshAccount>
  );
}
