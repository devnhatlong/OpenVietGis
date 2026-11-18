import { describe, expect, it } from "vitest";
import type { SpatialCrsRegistry, SpatialTransformationProfile } from "@openvietgis/client-sdk";
import { availableResponseCrs, crsRegistryMatchesScope, crsRegistryKey } from "./crs-profiles";
import { featurePageKey, featureResponseMatchesScope, reconcileTraversal, createTraversal, selectFeature, nextFeaturePage, type FeatureReadScope } from "./feature-inspector";

const edge: SpatialTransformationProfile = { source_code: 4326, target_code: 3857, operation_id: "exact", method: "explicit", validated_area: "world", tolerance: 0.001, tolerance_unit: "metre", evidence_id: "analytic" };
const scope: FeatureReadScope = { accountId: "u", organizationId: "o", projectId: "p", layerId: "l", sourceId: "s", contentRevision: "c", schemaRevision: "r", nativeCrs: 4326 };
const registry = { organization_id: "o", project_id: "p", profiles: [
  { code: 4326, disposition: "readable" }, { code: 3857, disposition: "readable" }, { code: 3405, disposition: "definition_only" }, { code: 5899, disposition: "readable" }
], transformations: [edge, { ...edge, source_code: 3857, target_code: 5899 }] } as SpatialCrsRegistry;

describe("current finite CRS controls", () => {
  it("offers native and direct approved edges only, never definition-only or graph transit", () => {
    expect(availableResponseCrs(registry, 4326)).toEqual([4326, 3857]);
    expect(availableResponseCrs(registry, 5899)).toEqual([5899]);
  });
  it("isolates discovery cache and checks both Project scope IDs", () => {
    expect(crsRegistryMatchesScope(scope, registry)).toBe(true);
    expect(crsRegistryMatchesScope({ ...scope, projectId: "foreign" }, registry)).toBe(false);
    expect(crsRegistryMatchesScope({ ...scope, organizationId: "foreign" }, registry)).toBe(false);
    expect(crsRegistryKey({ ...scope, accountId: "other" })).not.toEqual(crsRegistryKey(scope));
  });
  it("separates transformed cache keys and restarts pagination while retaining stable selection", () => {
    const changed = { ...scope, responseCrs: 3857, transformation: edge };
    const state = nextFeaturePage(selectFeature(reconcileTraversal(createTraversal(), scope), "point-000001"), "point-000020");
    expect(featurePageKey(changed, null)).not.toEqual(featurePageKey(scope, null));
    expect(reconcileTraversal(state, changed)).toMatchObject({ cursor: null, history: [], selected: "point-000001" });
  });
  it("requires exact operation evidence and target axes before exposing transformed data", () => {
    const transformedScope = { ...scope, responseCrs: 3857, transformation: edge };
    const context = { organization_id: "o", project_id: "p", layer_id: "l", source_id: "s", content_revision: "c", schema_revision: "r", geometry_included: true, response_crs: { authority: "EPSG", code: 3857, coordinate_order: "xy", x_axis: "easting", y_axis: "northing", unit: "metre" }, transformation: edge } as const;
    expect(featureResponseMatchesScope(transformedScope, context)).toBe(true);
    expect(featureResponseMatchesScope(transformedScope, { ...context, transformation: { ...edge, evidence_id: "wrong" } })).toBe(false);
    expect(featureResponseMatchesScope(transformedScope, { ...context, transformation: null })).toBe(false);
    expect(featureResponseMatchesScope(scope, context)).toBe(false);
  });
});
