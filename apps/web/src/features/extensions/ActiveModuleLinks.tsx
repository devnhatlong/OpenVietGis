import { listExtensionManifests, listProjectActivations } from "@openvietgis/client-sdk";
import { useQuery } from "@tanstack/react-query";
import { Link, NavLink } from "react-router-dom";
import { apiClient } from "../../app/api";

type Props = {
  organizationId: string;
  projectId: string;
  slot: "project_route" | "project_tool" | "project_panel";
  sourceId?: string | null;
  featureId?: string | null;
  variant?: "link" | "nav";
  collapsed?: boolean;
};

export function ActiveModuleLinks({
  organizationId,
  projectId,
  slot,
  sourceId,
  featureId,
  variant = "link",
  collapsed = false
}: Props) {
  const activations = useQuery({
    queryKey: ["module-links", organizationId, projectId, "activations"],
    queryFn: () => listProjectActivations(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });
  const manifests = useQuery({
    queryKey: ["module-links", organizationId, "manifests"],
    queryFn: () => listExtensionManifests(apiClient, organizationId),
    enabled: Boolean(organizationId)
  });
  const activeIds = new Set(
    (activations.data?.items ?? [])
      .filter((item) => item.status === "active")
      .map((item) => item.manifest_id)
  );
  const links = (manifests.data?.items ?? []).flatMap((manifest) => {
    if (!activeIds.has(manifest.id)) return [];
    return (manifest.ui_contributions ?? [])
      .filter((item) => item.slot === slot && typeof item.route_suffix === "string")
      .map((item) => ({
        id: `${manifest.id}:${String(item.id ?? item.route_suffix)}`,
        label: typeof item.label === "string" ? item.label : manifest.display_name,
        suffix: String(item.route_suffix)
      }));
  });

  return (
    <>
      {links.map((item) => {
        const query = new URLSearchParams();
        if (sourceId) query.set("sourceId", sourceId);
        if (featureId) query.set("featureId", featureId);
        const suffix = query.size ? `${item.suffix}?${query}` : item.suffix;
        const to = `/app/organizations/${encodeURIComponent(organizationId)}/projects/${encodeURIComponent(projectId)}${suffix}`;

        if (variant === "nav") {
          return (
            <NavLink
              key={item.id}
              to={to}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) => (isActive ? "is-active" : undefined)}
            >
              <span className="ovg-app-nav-icon" aria-hidden="true">
                <svg
                  width="17"
                  height="17"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.9"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 2 2 7l10 5 10-5-10-5Z" />
                  <path d="m2 17 10 5 10-5" />
                  <path d="m2 12 10 5 10-5" />
                </svg>
              </span>
              {collapsed ? null : <span className="ovg-app-nav-label">{item.label}</span>}
            </NavLink>
          );
        }

        return (
          <Link key={item.id} to={to} className="ovg-pill-link">
            {item.label}
          </Link>
        );
      })}
    </>
  );
}
