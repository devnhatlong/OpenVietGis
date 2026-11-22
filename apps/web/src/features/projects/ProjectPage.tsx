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

function projectStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    active: "Đang hoạt động",
    archived: "Đã lưu trữ",
    deleted: "Đã xóa"
  };
  return labels[status] ?? status;
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
    const checking =
      !projects.error &&
      !workspaces.error &&
      (projects.isPending ||
        projects.fetchStatus !== "idle" ||
        workspaces.isPending ||
        workspaces.fetchStatus !== "idle");
    return (
      <main className="w-full p-5 space-y-4">
        <div className="flex items-center gap-3 text-sm text-ink-muted">
          <Link to="/" className="hover:text-brand">← Tổ chức</Link>
        </div>
        <h1 className="text-xl font-extrabold tracking-tight text-ink">Dự án</h1>
        {checking ? (
          <p className="rounded-xl border border-line bg-surface p-4 text-sm text-ink-muted">
            Đang kiểm tra quyền truy cập dự án…
          </p>
        ) : (
          <p role="alert" className="rounded-xl border border-danger bg-danger-soft p-4 text-sm text-danger">
            Không thể tải quyền truy cập dự án.
          </p>
        )}
      </main>
    );
  }

  return (
    <main className="w-full p-5 space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-extrabold tracking-tight text-ink">Dự án</h1>
          <span className="rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-bold text-brand">
            {visibleProjects.length} dự án
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={"/app/organizations/" + organizationId}
            className="inline-flex items-center rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-xs font-semibold text-ink-secondary hover:border-brand hover:text-brand"
          >
            ← Tổ chức
          </Link>
          <Link
            to={"/app/organizations/" + organizationId + "/workspaces"}
            className="inline-flex items-center rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-xs font-semibold text-ink-secondary hover:border-brand hover:text-brand"
          >
            Không gian làm việc
          </Link>
        </div>
      </header>

      <section className="rounded-2xl border border-line bg-surface p-5 shadow-xs">
        <h2 className="mb-4 text-sm font-bold text-ink">Tạo dự án mới</h2>
        <form onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 items-end">
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-secondary">
            <span>Tên dự án</span>
            <input
              aria-label="Tên dự án"
              className="w-full"
              placeholder="Ví dụ: Bản đồ Quy hoạch 2026"
              value={name}
              onChange={(event) => {
                setName(event.target.value);
                if (!slug) setSlug(slugify(event.target.value));
              }}
              required
            />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-secondary">
            <span>Mã định danh dự án</span>
            <input
              aria-label="Mã định danh dự án"
              className="w-full"
              placeholder="ban-do-quy-hoach"
              value={slug}
              onChange={(event) => setSlug(event.target.value)}
              required
            />
          </label>
          <label className="flex flex-col gap-1.5 text-xs font-semibold text-ink-secondary">
            <span>Không gian làm việc</span>
            <select
              aria-label="Không gian làm việc của dự án"
              className="w-full"
              value={workspaceId}
              onChange={(event) => setWorkspaceId(event.target.value)}
            >
              <option value="">Chưa phân nhóm</option>
              {visibleWorkspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </label>
          <div>
            <button
              type="submit"
              disabled={create.isPending}
              className="inline-flex w-full items-center justify-center rounded-lg bg-brand px-4 py-2 text-sm font-bold text-brand-fg hover:bg-brand-strong disabled:opacity-50 cursor-pointer"
            >
              Tạo dự án
            </button>
          </div>
        </form>
        {create.error ? (
          <p role="alert" className="mt-3 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-xs font-medium text-danger">
            Không thể tạo dự án.
          </p>
        ) : null}
        {update.error ? (
          <p role="alert" className="mt-3 rounded-lg border border-danger bg-danger-soft px-3 py-2 text-xs font-medium text-danger">
            Không thể cập nhật dự án.
          </p>
        ) : null}
      </section>

      <section className="rounded-2xl border border-line bg-surface p-5 shadow-xs">
        <h2 className="mb-4 text-sm font-bold text-ink">Danh sách dự án</h2>
        <ul data-testid="project-list" className="grid grid-cols-1 gap-3 list-none p-0 m-0">
          {visibleProjects.map((project) => {
            const moveTarget = moveTargets[project.id] ?? project.workspace_id ?? "";
            const workspaceName = project.workspace_id
              ? visibleWorkspaces.find((workspace) => workspace.id === project.workspace_id)?.name ?? "Không gian làm việc không khả dụng"
              : "Chưa phân nhóm";
            const mapUrl =
              "/app/organizations/" +
              encodeURIComponent(organizationId) +
              "/projects/" +
              encodeURIComponent(project.id) +
              "/map";
            const spatialUrl =
              "/app/organizations/" +
              encodeURIComponent(organizationId) +
              "/projects/" +
              encodeURIComponent(project.id) +
              "/spatial";
            return (
              <li
                key={project.id}
                data-testid={"project-" + project.id}
                className="flex flex-col gap-4 rounded-xl border border-line bg-surface-muted p-4"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <strong className="text-base font-bold text-ink">{project.name}</strong>
                    <span className="rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-semibold text-brand">
                      {projectStatusLabel(project.status)}
                    </span>
                    <span className="rounded-full border border-line bg-surface px-2.5 py-0.5 text-xs text-ink-muted">
                      {workspaceName}
                    </span>
                  </div>
                  {project.status !== "deleted" ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={mapUrl}
                        className="inline-flex items-center rounded-lg bg-brand px-3.5 py-1.5 text-xs font-bold text-brand-fg hover:bg-brand-strong no-underline"
                      >
                        Mở Bản đồ
                      </Link>
                      <Link
                        to={spatialUrl}
                        className="inline-flex items-center rounded-lg border border-line-strong bg-surface px-3 py-1.5 text-xs font-semibold text-ink-secondary hover:border-brand hover:text-brand no-underline"
                      >
                        Danh mục Dữ liệu
                      </Link>
                    </div>
                  ) : null}
                </div>

                <div className="flex flex-wrap items-end gap-3 border-t border-line pt-3">
                  <label className="flex flex-col gap-1 text-xs font-medium text-ink-muted min-w-[220px]">
                    <span>Không gian làm việc của {project.name}</span>
                    <select
                      aria-label={"Không gian làm việc của " + project.name}
                      value={moveTarget}
                      onChange={(event) =>
                        setMoveTargets((current) => ({
                          ...current,
                          [project.id]: event.target.value
                        }))
                      }
                    >
                      <option value="">Chưa phân nhóm</option>
                      {visibleWorkspaces.map((workspace) => (
                        <option key={workspace.id} value={workspace.id}>
                          {workspace.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="rounded-lg border border-line-strong bg-surface px-3 py-2 text-xs font-semibold text-ink-secondary hover:border-brand hover:text-brand cursor-pointer"
                    onClick={() =>
                      update.mutate({
                        projectId: project.id,
                        input: { workspace_id: moveTarget || null }
                      })
                    }
                  >
                    Chuyển nhóm {project.name}
                  </button>
                  <button
                    type="button"
                    className="rounded-lg border border-line-strong bg-surface px-3 py-2 text-xs font-semibold text-ink-secondary hover:border-brand hover:text-brand cursor-pointer"
                    onClick={() =>
                      update.mutate({
                        projectId: project.id,
                        input: { workspace_id: null }
                      })
                    }
                  >
                    Bỏ khỏi nhóm {project.name}
                  </button>
                  {project.status === "active" ? (
                    <button
                      type="button"
                      className="rounded-lg border border-danger/40 bg-surface px-3 py-2 text-xs font-semibold text-danger hover:bg-danger-soft cursor-pointer"
                      onClick={() =>
                        update.mutate({
                          projectId: project.id,
                          input: { status: "archived" }
                        })
                      }
                    >
                      Lưu trữ {project.name}
                    </button>
                  ) : project.status === "archived" ? (
                    <button
                      type="button"
                      className="rounded-lg border border-brand bg-brand-soft px-3 py-2 text-xs font-semibold text-brand hover:bg-brand hover:text-brand-fg cursor-pointer"
                      onClick={() =>
                        update.mutate({
                          projectId: project.id,
                          input: { status: "active" }
                        })
                      }
                    >
                      Khôi phục {project.name}
                    </button>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      </section>
    </main>
  );
}

export function ProjectPage() {
  const { organizationId } = useParams();
  if (!organizationId) return <p role="alert">Thiếu ngữ cảnh tổ chức.</p>;
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
