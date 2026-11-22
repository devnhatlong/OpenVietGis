import { listExtensionManifests, listProjectActivations } from "@openvietgis/client-sdk";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiClient } from "../../app/api";

type Props = {
  organizationId: string;
  projectId: string;
  slot: "project_route" | "project_tool" | "project_panel";
  sourceId?: string | null;
  featureId?: string | null;
};

export function ActiveModuleLinks({ organizationId, projectId, slot, sourceId, featureId }: Props) {
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
    (activations.data?.items ?? []).filter((item) => item.status === "active").map((item) => item.manifest_id)
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
  return <>{links.map((item) => {
    const query = new URLSearchParams();
    if (sourceId) query.set("sourceId", sourceId);
    if (featureId) query.set("featureId", featureId);
    const suffix = query.size ? `${item.suffix}?${query}` : item.suffix;
    return <Link key={item.id} to={`/organizations/${organizationId}/projects/${projectId}${suffix}`}>{item.label}</Link>;
  })}</>;
}
