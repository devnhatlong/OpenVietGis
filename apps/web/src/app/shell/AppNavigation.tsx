import { NavLink, useLocation, useParams } from "react-router-dom";

import { buildNavigationItems } from "./navigation-model";

export function AppNavigation({ collapsed }: { collapsed: boolean }) {
  const { organizationId, projectId } = useParams();
  const location = useLocation();
  const items = buildNavigationItems(organizationId, projectId).filter(
    (item) => item.availability !== "omitted"
  );
  const currentFull = location.pathname + location.search;

  return (
    <nav className="ovg-app-nav" aria-label="Điều hướng chính">
      {items.map((item) => {
        const hasQuery = item.destination.includes("?");
        return (
          <NavLink
            key={item.id}
            to={item.destination}
            end={item.destination === "/app"}
            title={collapsed ? item.labelKey : undefined}
            aria-disabled={item.availability === "disabled" ? true : undefined}
            onClick={(event) => {
              if (item.availability === "disabled") event.preventDefault();
            }}
            className={({ isActive }) => {
              const active = hasQuery ? currentFull === item.destination : isActive && !location.search;
              return active ? "is-active" : undefined;
            }}
          >
            <span className="ovg-app-nav-icon" aria-hidden="true">{item.short}</span>
            {collapsed ? null : <span>{item.labelKey}</span>}
          </NavLink>
        );
      })}
    </nav>
  );
}
