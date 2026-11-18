import { listSpatialCrsProfiles } from "@openvietgis/client-sdk";
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../app/api";
import { currentProtectedData, protectedQueryOptions } from "../../app/protected-query";
import { crsRegistryKey, crsRegistryMatchesScope, type CrsScope } from "./crs-profiles";

export function CrsRegistryPanel({ scope }: { scope: CrsScope }) {
  const query = useQuery({ queryKey: crsRegistryKey(scope),
    queryFn: () => listSpatialCrsProfiles(apiClient, scope.organizationId, scope.projectId),
    ...protectedQueryOptions });
  const registry = currentProtectedData(query);
  if (!registry) return <p role={query.error ? "alert" : "status"}>{query.error
    ? "Unable to verify current CRS profile access." : "Checking current CRS profiles…"}</p>;
  if (!crsRegistryMatchesScope(scope, registry)) return <p role="alert">CRS profiles do not match the current Project.</p>;
  return <section aria-label="Coordinate reference support">
    <h2>Coordinate reference support</h2>
    <p>Application coordinates use X/Y order. Native EPSG axes and units are listed separately.</p>
    <details><summary>CRS definitions and approved operations</summary>
      <div style={{ overflowX: "auto" }}><table aria-label="CRS definitions"><thead><tr>
        <th>CRS</th><th>Native axes</th><th>Application X/Y</th><th>Unit</th><th>Support</th><th>Area</th>
      </tr></thead><tbody>{registry.profiles.map(profile => <tr key={profile.code}>
        <th>EPSG:{profile.code} — {profile.name}</th><td>{profile.native_axes.join(", ")}</td>
        <td>{profile.x_axis}, {profile.y_axis}</td><td>{profile.unit}</td>
        <td>{profile.disposition === "definition_only" ? "Definition only" : "Readable"}</td><td>{profile.area_of_use}</td>
      </tr>)}</tbody></table></div>
      <ul aria-label="Approved direct operations">{registry.transformations.map(edge => <li key={edge.operation_id}>
        EPSG:{edge.source_code} → EPSG:{edge.target_code}: {edge.method}; tolerance {edge.tolerance} {edge.tolerance_unit}.
        {" "}{edge.validated_area} Evidence: {edge.evidence_id}.
      </li>)}</ul>
    </details>
  </section>;
}
