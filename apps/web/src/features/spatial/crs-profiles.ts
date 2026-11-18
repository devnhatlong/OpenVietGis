import type { SpatialCrsRegistry } from "@openvietgis/client-sdk";

export interface CrsScope { accountId: string; organizationId: string; projectId: string }
export function crsRegistryKey(scope: CrsScope) {
  return ["spatial-catalog", scope.accountId, scope.organizationId, scope.projectId, "crs-profiles"] as const;
}
export function crsRegistryMatchesScope(scope: CrsScope, registry: SpatialCrsRegistry): boolean {
  return registry.organization_id === scope.organizationId && registry.project_id === scope.projectId;
}
export function availableResponseCrs(registry: SpatialCrsRegistry, nativeCrs: number): number[] {
  const readable = new Set<number>(registry.profiles.filter(profile => profile.disposition === "readable").map(profile => profile.code));
  if (!readable.has(nativeCrs)) return [];
  return [nativeCrs, ...registry.transformations.filter(edge => edge.source_code === nativeCrs && readable.has(edge.target_code))
    .map(edge => edge.target_code)].filter((code, index, all) => all.indexOf(code) === index);
}
