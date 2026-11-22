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

function workspaceStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "Đang hoạt động",
    archived: "Đã lưu trữ",
    deleted: "Đã xóa"
  };
  return labels[status] ?? status;
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
      <main className="w-full p-5 space-y-4">
        <Link to="/" className="text-sm text-ink-muted hover:text-brand">← Tổ chức</Link>
        <h1 className="text-xl font-extrabold text-ink">Không gian làm việc</h1>
        {checking ? (
          <p className="rounded-xl border border-line bg-surface p-4 text-sm text-ink-muted">
            Đang kiểm tra quyền truy cập không gian làm việc…
          </p>
        ) : (
          <p role="alert" className="rounded-xl border border-danger bg-danger-soft p-4 text-sm text-danger">
            Không thể tải quyền truy cập không gian làm việc.
          </p>
        )}
      </main>
    );
  }

  return (
    <main className="w-full p-5 space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-extrabold tracking-tight text-ink">Không gian làm việc</h1>
          <span className="rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-bold text-brand">
            {visibleWorkspaces.length} nhóm
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to={"/app/organizations/" + organizationId}
            className="inline-flex items-center rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-xs font-semibold text-ink-secondary hover:border-brand hover:text-brand"
          >
            ← Tổ chức
          </Link>
          <Link
            to={"/app/organizations/" + organizationId + "/projects"}
            className="inline-flex items-center rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-xs font-semibold text-ink-secondary hover:border-brand hover:text-brand"
          >
            Dự án
          </Link>
        </div>
      </header>

      <section className="rounded-2xl border border-line bg-surface p-5 shadow-xs">
        <h2 className="mb-4 text-sm font-bold text-ink">Tạo không gian làm việc</h2>
        <form onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-3 items-end">
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-secondary">
            <span>Tên không gian làm việc</span>
            <input
              aria-label="Tên không gian làm việc"
              className="w-full"
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                if (!slug) setSlug(slugify(event.target.value));
              }}
              required
            />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-secondary">
            <span>Mã định danh</span>
            <input
              aria-label="Mã định danh"
              className="w-full"
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
              required
            />
          </label>
          <div>
            <button
              type="submit"
              disabled={create.isPending}
              className="inline-flex w-full items-center justify-center rounded-lg bg-brand px-4 py-2 text-sm font-bold text-brand-fg hover:bg-brand-strong disabled:opacity-50 cursor-pointer"
            >
              Tạo không gian làm việc
            </button>
          </div>
        </form>
        {create.error ? (
          <p role="alert" className="mt-3 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-xs text-danger">
            Không thể tạo không gian làm việc.
          </p>
        ) : null}
        {changeStatus.error ? (
          <p role="alert" className="mt-3 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-xs text-danger">
            Không thể thay đổi trạng thái không gian làm việc.
          </p>
        ) : null}
      </section>

      <section className="rounded-2xl border border-line bg-surface p-5 shadow-xs">
        <h2 className="mb-4 text-sm font-bold text-ink">Danh sách không gian làm việc</h2>
        <ul data-testid="workspace-list" className="grid grid-cols-1 gap-3 list-none p-0 m-0">
          {visibleWorkspaces.map((workspace) => (
            <li
              key={workspace.id}
              data-testid={"workspace-" + workspace.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface-muted p-4"
            >
              <div className="flex items-center gap-2.5">
                <strong className="text-sm font-bold text-ink">{workspace.name}</strong>
                <span className="rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-semibold text-brand">
                  {workspaceStatusLabel(workspace.status)}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {workspace.status === "active" ? (
                  <button
                    type="button"
                    className="rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-xs font-semibold text-ink-secondary hover:border-brand hover:text-brand cursor-pointer"
                    onClick={() =>
                      changeStatus.mutate({ workspaceId: workspace.id, status: "archived" })
                    }
                  >
                    Lưu trữ {workspace.name}
                  </button>
                ) : workspace.status === "archived" ? (
                  <button
                    type="button"
                    className="rounded-lg border border-brand bg-brand-soft px-3 py-1.5 text-xs font-semibold text-brand cursor-pointer"
                    onClick={() =>
                      changeStatus.mutate({ workspaceId: workspace.id, status: "active" })
                    }
                  >
                    Khôi phục {workspace.name}
                  </button>
                ) : null}
                <button
                  type="button"
                  className="rounded-lg border border-danger/40 bg-surface px-3 py-1.5 text-xs font-semibold text-danger hover:bg-danger-soft cursor-pointer"
                  onClick={() =>
                    changeStatus.mutate({ workspaceId: workspace.id, status: "deleted" })
                  }
                >
                  Xóa {workspace.name}
                </button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

export function WorkspacePage() {
  const { organizationId } = useParams();
  if (!organizationId) return <p role="alert">Thiếu ngữ cảnh tổ chức.</p>;
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
