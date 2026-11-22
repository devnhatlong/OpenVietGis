import {
  getBootstrapStatus,
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
import { ActiveModuleLinks } from "../extensions/ActiveModuleLinks";
import { BootstrapPage } from "../organizations/BootstrapPage";
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

  const bootstrapQuery = useQuery({
    queryKey: ["bootstrap-status"],
    queryFn: () => getBootstrapStatus(apiClient),
    ...protectedQueryOptions
  });

  const organizationsQuery = useQuery({
    queryKey: ["my-organizations", account.id],
    queryFn: () => listMyOrganizations(apiClient),
    ...protectedQueryOptions
  });

  const bootstrap = currentProtectedData(bootstrapQuery);
  const organizations = currentProtectedData(organizationsQuery);

  const projectQueries = useQueries({
    queries: (organizations ?? []).map((organization) => ({
      queryKey: ["projects", organization.id, account.id],
      queryFn: () => listProjects(apiClient, organization.id),
      ...protectedQueryOptions
    }))
  });

  if (!bootstrap) {
    const checking =
      !bootstrapQuery.error &&
      (bootstrapQuery.isPending || bootstrapQuery.fetchStatus !== "idle");
    return (
      <section className="dashboard-page">
        <div className="dashboard-state" role={checking ? "status" : "alert"}>
          {checking
            ? "Đang kiểm tra trạng thái hệ thống…"
            : "Không thể kiểm tra trạng thái hệ thống."}
        </div>
      </section>
    );
  }

  if (!bootstrap.initialized) {
    return (
      <BootstrapPage
        onInitialized={async () => {
          await Promise.all([
            bootstrapQuery.refetch(),
            organizationsQuery.refetch()
          ]);
        }}
      />
    );
  }

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
  const archivedCount = projects.filter(
    ({ project }) => project.status === "archived"
  ).length;
  const primaryProject = activeProjects[0] ?? projects[0] ?? null;

  return (
    <main className="dashboard-page">
      <section className="dashboard-hero">
        <div className="dashboard-hero-grid" aria-hidden="true" />
        <div className="dashboard-hero-body">
          <div className="dashboard-hero-copy">
            <span className="dashboard-kicker">OPENVietGIS STUDIO · KHÔNG GIAN LÀM VIỆC</span>
            <h1>Chào {account.display_name}</h1>
            <p>
              Trung tâm điều hành bản đồ GIS, biên tập PostGIS, chuyển đổi AutoCAD DXF/COGO,
              tích hợp WMS/COG bên thứ 3 và các mô-đun nghiệp vụ chuyên sâu.
            </p>
          </div>
          {primaryProject ? (
            <div className="dashboard-hero-cta">
              <Link
                className="dashboard-cta-primary"
                to={`/app/organizations/${encodeURIComponent(primaryProject.organization.id)}/projects/${encodeURIComponent(primaryProject.project.id)}/map`}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21" />
                  <line x1="9" y1="3" x2="9" y2="18" />
                  <line x1="15" y1="6" x2="15" y2="21" />
                </svg>
                <span>Mở Không gian Bản đồ</span>
              </Link>
              <Link
                className="dashboard-cta-secondary"
                to={`/app/organizations/${encodeURIComponent(primaryProject.organization.id)}/projects/${encodeURIComponent(primaryProject.project.id)}/map?tool=cad`}
              >
                <span>AutoCAD & COGO</span>
              </Link>
            </div>
          ) : null}
        </div>
      </section>

      <section className="dashboard-metrics" aria-label="Tổng quan">
        <article className="metric-card is-teal">
          <div className="metric-head">
            <span>Tổ chức</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><path d="M3 21h18" /><path d="M5 21V7l8-4v18" /><path d="M19 21V11l-6-4" /></svg>
          </div>
          <strong>{organizations.length}</strong>
          <small>được phép truy cập</small>
        </article>
        <article className="metric-card is-blue">
          <div className="metric-head">
            <span>Dự án GIS</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 12 12 17 22 12" /><polyline points="2 17 12 22 22 17" /></svg>
          </div>
          <strong>{projects.length}</strong>
          <small>{activeProjects.length} đang hoạt động</small>
        </article>
        <article className="metric-card is-amber">
          <div className="metric-head">
            <span>Dự án đã lưu trữ</span>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true"><rect x="2" y="4" width="20" height="5" rx="2" /><path d="M4 9v9a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9" /><path d="M10 13h4" /></svg>
          </div>
          <strong>{archivedCount}</strong>
          <small>có thể khôi phục theo quyền</small>
        </article>
      </section>

      <div className="dashboard-grid">
        <section className="dashboard-card">
          <div className="dashboard-card-head">
            <div>
              <h2>Dự án & Phân hệ chuyên môn</h2>
              <p>Chọn nhanh không gian làm việc GIS, AutoCAD, nguồn bên thứ 3 hoặc mô-đun đang kích hoạt.</p>
            </div>
          </div>

          {projectGroups.some((group) => group.loading) && !projects.length ? (
            <p className="dashboard-muted">Đang tải danh sách dự án…</p>
          ) : projects.length ? (
            <div className="dashboard-projects">
              {projects.map(({ project, organization }) => {
                const base =
                  "/app/organizations/" +
                  encodeURIComponent(organization.id) +
                  "/projects/" +
                  encodeURIComponent(project.id);
                return (
                  <article key={project.id} className="dashboard-project-card">
                    <div className="dashboard-project-top">
                      <div className="dashboard-project-main">
                        <span
                          className={
                            project.status === "active"
                              ? "dashboard-dot is-active"
                              : "dashboard-dot"
                          }
                          aria-hidden="true"
                        />
                        <div>
                          <strong>{project.name}</strong>
                          <small>
                            {organization.name} · {projectStatusLabel(project.status)}
                          </small>
                        </div>
                      </div>
                      <Link className="dashboard-open-map" to={base + "/map"}>
                        Mở bản đồ →
                      </Link>
                    </div>

                    <div className="dashboard-bento-modules">
                      <div className="bento-tile">
                        <div className="bento-tile-head">
                          <span className="bento-icon is-teal" aria-hidden="true">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21" /></svg>
                          </span>
                          <div>
                            <h3>Bản đồ & Chuyên môn GIS</h3>
                            <p>Biên tập hình học, lọc thuộc tính, Buffer/Clip & in ấn</p>
                          </div>
                        </div>
                        <div className="bento-links">
                          <Link to={base + "/map"}>Bản đồ GIS</Link>
                          <Link to={base + "/map?tool=editing"}>Biên tập</Link>
                          <Link to={base + "/map?tool=queries"}>Truy vấn</Link>
                          <Link to={base + "/map?tool=processing"}>Buffer/Clip</Link>
                          <Link to={base + "/map?tool=cartography"}>In ấn</Link>
                        </div>
                      </div>

                      <div className="bento-tile">
                        <div className="bento-tile-head">
                          <span className="bento-icon is-blue" aria-hidden="true">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3 2 21h20L12 3Z" /><path d="M12 10v7" /></svg>
                          </span>
                          <div>
                            <h3>AutoCAD DXF & COGO</h3>
                            <p>Chuyển đổi bản vẽ CAD 2D VN-2000 & tính trắc địa</p>
                          </div>
                        </div>
                        <div className="bento-links">
                          <Link to={base + "/map?tool=cad"}>Mở AutoCAD / DXF & COGO</Link>
                        </div>
                      </div>

                      <div className="bento-tile">
                        <div className="bento-tile-head">
                          <span className="bento-icon is-indigo" aria-hidden="true">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 3a14 14 0 0 1 0 18" /></svg>
                          </span>
                          <div>
                            <h3>Tích hợp Bên thứ 3 & Dữ liệu</h3>
                            <p>WMS/WMTS/COG/WFS, hệ tọa độ CRS & GeoPackage</p>
                          </div>
                        </div>
                        <div className="bento-links">
                          <Link to={base + "/map?tool=external"}>WMS / COG / WFS</Link>
                          <Link to={base + "/map?tool=spatial"}>Danh mục & CRS</Link>
                          <Link to={base + "/map?tool=transfers"}>Nhập / Xuất</Link>
                        </div>
                      </div>

                      <div className="bento-tile">
                        <div className="bento-tile-head">
                          <span className="bento-icon is-amber" aria-hidden="true">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 12 12 17 22 12" /><polyline points="2 17 12 22 22 17" /></svg>
                          </span>
                          <div>
                            <h3>Mô-đun Mở rộng & Thực địa</h3>
                            <p>Plugin nghiệp vụ kích hoạt theo dự án & đồng bộ Offline</p>
                          </div>
                        </div>
                        <div className="bento-links">
                          <ActiveModuleLinks
                            organizationId={organization.id}
                            projectId={project.id}
                            slot="project_route"
                          />
                          <Link to={base + "/map?tool=field"}>Thực địa Offline</Link>
                          <Link to={base + "/map?tool=extensions"}>Quản lý Plugin</Link>
                        </div>
                      </div>
                    </div>
                  </article>
                );
              })}
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
              <p>Chọn phạm vi quản trị & phân quyền.</p>
            </div>
          </div>
          <div className="dashboard-organizations">
            {organizations.length ? (
              organizations.map((organization) => (
                <Link
                  key={organization.id}
                  to={"/app/organizations/" + encodeURIComponent(organization.id)}
                >
                  <div>
                    <strong>{organization.name}</strong>
                    <small>{roleLabel(organization.role)}</small>
                  </div>
                  <span className="dashboard-org-arrow" aria-hidden="true">→</span>
                </Link>
              ))
            ) : (
              <div className="dashboard-empty">
                <strong>Chưa có tổ chức</strong>
                <span>Tài khoản hiện tại chưa được cấp vào tổ chức nào.</span>
              </div>
            )}
          </div>
        </aside>
      </div>
    </main>
  );
}
