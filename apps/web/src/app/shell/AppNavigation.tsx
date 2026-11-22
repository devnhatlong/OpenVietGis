import { NavLink, useLocation, useParams } from "react-router-dom";
import { ActiveModuleLinks } from "../../features/extensions/ActiveModuleLinks";

import {
  buildNavigationItems,
  type AppNavigationItem,
  type NavigationGroup
} from "./navigation-model";

const GROUP_LABELS: Record<NavigationGroup, string> = {
  workspace: "Không gian làm việc",
  gis: "Chuyên môn GIS & AutoCAD",
  data: "Dữ liệu & Tích hợp",
  admin: "Cộng tác & Quản trị"
};

function NavIcon({ id }: { id: string }) {
  const props = {
    width: 17,
    height: 17,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.9,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const
  };
  switch (id) {
    case "overview":
      return <svg {...props}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /></svg>;
    case "map":
      return <svg {...props}><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21" /><line x1="9" y1="3" x2="9" y2="18" /><line x1="15" y1="6" x2="15" y2="21" /></svg>;
    case "autocad":
      return <svg {...props}><path d="M12 3 2 21h20L12 3Z" /><path d="M12 10v7" /><circle cx="12" cy="14" r="2" /></svg>;
    case "external-sources":
      return <svg {...props}><circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 3a14 14 0 0 1 0 18" /><path d="M12 3a14 14 0 0 0 0 18" /></svg>;
    case "editing":
      return <svg {...props}><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>;
    case "queries":
      return <svg {...props}><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>;
    case "processing":
      return <svg {...props}><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 12 12 17 22 12" /><polyline points="2 17 12 22 22 17" /></svg>;
    case "cartography":
      return <svg {...props}><polyline points="6 9 6 2 18 2 18 9" /><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" /><rect x="6" y="14" width="12" height="8" /></svg>;
    case "spatial":
      return <svg {...props}><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14a9 3 0 0 0 18 0V5" /><path d="M3 12a9 3 0 0 0 18 0" /></svg>;
    case "transfers":
      return <svg {...props}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>;
    case "field-offline":
      return <svg {...props}><rect x="5" y="2" width="14" height="20" rx="2" /><line x1="12" y1="18" x2="12.01" y2="18" /></svg>;
    case "collab":
      return <svg {...props}><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>;
    case "projects":
      return <svg {...props}><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>;
    case "workspaces":
      return <svg {...props}><rect x="3" y="4" width="18" height="16" rx="2" /><line x1="3" y1="10" x2="21" y2="10" /></svg>;
    case "membership":
      return <svg {...props}><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>;
    default:
      return <svg {...props}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9c.26.6.85 1 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>;
  }
}

export function AppNavigation({ collapsed }: { collapsed: boolean }) {
  const { organizationId, projectId } = useParams();
  const location = useLocation();
  const items = buildNavigationItems(organizationId, projectId).filter(
    (item) => item.availability !== "omitted"
  );
  const currentFull = location.pathname + location.search;

  const groupOrder: NavigationGroup[] = ["workspace", "gis", "data", "admin"];
  const grouped: Array<{ key: NavigationGroup; items: AppNavigationItem[] }> = groupOrder
    .map((key) => ({ key, items: items.filter((i) => (i.group ?? "workspace") === key) }))
    .filter((g) => g.items.length > 0);

  return (
    <nav className="ovg-app-nav" aria-label="Điều hướng chính">
      {grouped.map((group) => (
        <div key={group.key} className="ovg-nav-group">
          {!collapsed && <div className="ovg-nav-group-label">{GROUP_LABELS[group.key]}</div>}
          {group.items.map((item) => {
            const hasQuery = item.destination.includes("?");
            return (
              <NavLink
                key={item.id}
                to={item.destination}
                end={item.destination === "/app" || item.id === "projects"}
                title={collapsed ? item.labelKey : undefined}
                aria-disabled={item.availability === "disabled" ? true : undefined}
                onClick={(event) => {
                  if (item.availability === "disabled") event.preventDefault();
                }}
                className={({ isActive }) => {
                  const active = hasQuery
                    ? currentFull === item.destination
                    : isActive && !location.search;
                  return active ? "is-active" : undefined;
                }}
              >
                <span className="ovg-app-nav-icon" aria-hidden="true">
                  <NavIcon id={item.id} />
                </span>
                {collapsed ? null : <span className="ovg-app-nav-label">{item.labelKey}</span>}
              </NavLink>
            );
          })}
          {group.key === "workspace" && organizationId && projectId ? (
            <ActiveModuleLinks
              organizationId={organizationId}
              projectId={projectId}
              slot="project_route"
              variant="nav"
              collapsed={collapsed}
            />
          ) : null}
        </div>
      ))}
    </nav>
  );
}
