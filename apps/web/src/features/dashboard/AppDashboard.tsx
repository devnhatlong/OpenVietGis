import {
  listMyOrganizations,
  listProjects,
  type MyOrganization,
  type Project
} from "@openvietgis/client-sdk";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiClient } from "../../app/api";
import {
  currentProtectedData,
  protectedQueryOptions
} from "../../app/protected-query";
import { useSession } from "../../app/session/SessionBoundary";
import "./dashboard.css";

function roleLabel(role: MyOrganization["role"]): string {
  return {
    owner: "Chủ sở hữu",
    admin: "Quản trị viên",
    member: "Thành viên",
    guest: "Khách"
  }[role];
}

function projectStatusLabel(status: Project["status"]): string {
  return {
    active: "Đang hoạt động",
    archived: "Đã lưu trữ",
    deleted: "Đã xóa"
  }[status];
}

export function AppDashboard() {
  const { account } = useSession();

  const organizationsQuery = useQuery({
    queryKey: ["my-organizations", account.id],
    queryFn: () => listMyOrganizations(apiClient),
    ...protectedQueryOptions
  });

  const organizations = currentProtectedData(organizationsQuery);

  const projectQueries = useQueries({
    queries: (organizations ?? []).map((organization) => ({
      queryKey: ["projects", organization.id, account.id],
      queryFn: () => listProjects(apiClient, organization.id),
      ...protectedQueryOptions
    }))
  });

  if (!organizations) {
    const checking =
      !organizationsQuery.error &&
      (organizationsQuery.isPending || organizationsQuery.fetchStatus !== "idle");
    return (
      <section className="dashboard-page">
        <div className="dashboard-state" role={checking ? "status" : "alert"}>
          {checking
            ? "Đang kiểm tra tổ chức và dự án được phép truy cập…"
            : "Không thể tải không gian làm việc hiện tại."}
        </div>
      </section>
    );
  }

  const projectGroups = organizations.map((organization, index) => {
    const query = projectQueries[index];
    const projects = query ? currentProtectedData(query) : undefined;
    return {
      organization,
      projects: projects ?? [],
      loading:
        !projects &&
        Boolean(
          query &&
            !query.error &&
            (query.isPending || query.fetchStatus !== "idle")
        )
    };
  });

  const projects = projectGroups
    .flatMap(({ organization, projects: items }) =>
      items.map((project) => ({ project, organization }))
    )
    .filter(({ project }) => project.status !== "deleted");

  const activeProjects = projects.filter(
    ({ project }) => project.status === "active"
  );

  return (
    <main className="dashboard-page">
      <section className="dashboard-heading">
        <div>
          <span className="dashboard-kicker">KHÔNG GIAN LÀM VIỆC</span>
          <h1>Chào {account.display_name}</h1>
          <p>
            Mở nhanh dự án gần đây hoặc chọn một tổ chức để quản lý dữ liệu GIS,
            thành viên và quyền truy cập.
          </p>
        </div>
      </section>

      <section className="dashboard-metrics" aria-label="Tổng quan">
        <article>
          <span>Tổ chức</span>
          <strong>{organizations.length}</strong>
          <small>được phép truy cập</small>
        </article>
        <article>
          <span>Dự án</span>
          <strong>{projects.length}</strong>
          <small>{activeProjects.length} đang hoạt động</small>
        </article>
        <article>
          <span>Dự án đã lưu trữ</span>
          <strong>
            {projects.filter(({ project }) => project.status === "archived").length}
          </strong>
          <small>có thể khôi phục theo quyền</small>
        </article>
      </section>

      <div className="dashboard-grid">
        <section className="dashboard-card">
          <div className="dashboard-card-head">
            <div>
              <h2>Dự án</h2>
              <p>Mở trực tiếp bản đồ hoặc dữ liệu của các dự án bạn có quyền.</p>
            </div>
          </div>

          {projectGroups.some((group) => group.loading) ? (
            <p className="dashboard-muted" role="status">
              Đang kiểm tra các dự án được phép truy cập…
            </p>
          ) : null}

          {projects.length ? (
            <div className="dashboard-projects">
              {projects.map(({ project, organization }) => (
                <article key={project.id}>
                  <div className="dashboard-project-main">
                    <span
                      className={
                        project.status === "active"
                          ? "dashboard-dot is-active"
                          : "dashboard-dot"
                      }
                    />
                    <div>
                      <strong>{project.name}</strong>
                      <small>
                        {organization.name} · {projectStatusLabel(project.status)}
                      </small>
                    </div>
                  </div>
                  {project.status !== "deleted" ? (
                    <div className="dashboard-project-actions">
                      <Link
                        to={
                          "/app/organizations/" +
                          encodeURIComponent(organization.id) +
                          "/projects/" +
                          encodeURIComponent(project.id) +
                          "/map"
                        }
                      >
                        Mở bản đồ
                      </Link>
                      <Link
                        to={
                          "/app/organizations/" +
                          encodeURIComponent(organization.id) +
                          "/projects/" +
                          encodeURIComponent(project.id) +
                          "/spatial"
                        }
                      >
                        Dữ liệu GIS
                      </Link>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="dashboard-empty">
              <strong>Chưa có dự án khả dụng</strong>
              <span>
                Chọn một tổ chức để tạo dự án hoặc chờ quản trị viên cấp quyền.
              </span>
            </div>
          )}
        </section>

        <aside className="dashboard-card">
          <div className="dashboard-card-head">
            <div>
              <h2>Tổ chức</h2>
              <p>Chọn phạm vi làm việc.</p>
            </div>
          </div>
          <div className="dashboard-organizations">
            {organizations.length ? (
              organizations.map((organization) => (
                <Link
                  key={organization.id}
                  to={
                    "/app/organizations/" +
                    encodeURIComponent(organization.id)
                  }
                >
                  <div>
                    <strong>{organization.name}</strong>
                    <small>{roleLabel(organization.role)}</small>
                  </div>
                  <span aria-hidden="true">→</span>
                </Link>
              ))
            ) : (
              <div className="dashboard-empty">
                <strong>Chưa có tổ chức</strong>
                <span>
                  Tài khoản hiện tại chưa được cấp vào tổ chức nào.
                </span>
              </div>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
