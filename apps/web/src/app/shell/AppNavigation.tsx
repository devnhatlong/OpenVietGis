import { NavLink, useParams } from "react-router-dom";

interface NavItem {
  label: string;
  to: string;
  short: string;
}

export function AppNavigation({ collapsed }: { collapsed: boolean }) {
  const { organizationId, projectId } = useParams();
  const items: NavItem[] = [
    { label: "Tổng quan", short: "TQ", to: "/app" }
  ];

  if (organizationId) {
    const org = "/app/organizations/" + encodeURIComponent(organizationId);
    items.push(
      { label: "Dự án", short: "DA", to: org + "/projects" },
      { label: "Không gian làm việc", short: "KG", to: org + "/workspaces" },
      { label: "Thành viên & phân quyền", short: "TV", to: org + "/membership" }
    );

    if (projectId) {
      const project = org + "/projects/" + encodeURIComponent(projectId);
      items.splice(
        2,
        0,
        { label: "Bản đồ", short: "BD", to: project + "/map" },
        { label: "Dữ liệu GIS", short: "DL", to: project + "/spatial" },
        { label: "Nhập / Xuất", short: "NX", to: project + "/transfers" },
        { label: "Công cụ", short: "CC", to: project + "/platform-hub" }
      );
    }
  }

  return (
    <nav className="ovg-app-nav" aria-label="Điều hướng chính">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/app"}
          title={collapsed ? item.label : undefined}
          className={({ isActive }) => isActive ? "is-active" : undefined}
        >
          <span className="ovg-app-nav-icon" aria-hidden="true">{item.short}</span>
          {collapsed ? null : <span>{item.label}</span>}
        </NavLink>
      ))}
    </nav>
  );
}
