import { describe, expect, it } from "vitest";
import type { MapViewport } from "@openvietgis/client-sdk";
import { createViewportFramePreparer, isImmutableViewportFeatures } from "./render-frame";

const scope = { accountId: "actor", organizationId: "org", projectId: "project", layerId: "layer",
  sourceId: "source", contentRevision: "content", schemaRevision: "schema" };
const crs = { authority: "EPSG", code: 4326, coordinate_order: "xy", x_axis: "longitude",
  y_axis: "latitude", unit: "degree" } as const;
function response(): MapViewport {
  return {
    context: { organization_id: scope.organizationId, project_id: scope.projectId,
      layer_id: scope.layerId, source_id: scope.sourceId, content_revision: scope.contentRevision,
      schema_revision: scope.schemaRevision, geometry_included: true, response_crs: crs, transformation: null },
    items: [
      { feature_id: "point-1", geometry: { type: "Point", coordinates: [105, 10], coordinate_reference: crs } }
    ],
    complete: true, limitation: null
  };
}
describe("current viewport immutable frame preparation", () => {
  it("prepares an exact authorized response once within the same success generation", () => {
    const prepare = createViewportFramePreparer(), value = response();
    const first = prepare(scope, value, 1);
    expect(first.status).toBe("ready");
    expect(prepare(scope, value, 1)).toBe(first);
    expect(first.status === "ready" && isImmutableViewportFeatures(first.features)).toBe(true);
    if (first.status !== "ready") throw new Error("fixture invalid");
    expect(Object.isFrozen(first.features)).toBe(true);
    expect(Object.isFrozen(first.features[0]!.geometry)).toBe(true);
    expect(Object.isFrozen(first.features[0]!.geometry.coordinates)).toBe(true);
    // An arbitrary shallow-frozen array is not trusted by the independent adapter.
    expect(isImmutableViewportFeatures(Object.freeze([...first.features]))).toBe(false);
    expect(Object.isFrozen(value.items[0]!.geometry.coordinates)).toBe(false);
  });

  it("does not reuse prior actor/pin context and never returns geometry for a delayed or mismatched response", () => {
    const prepare = createViewportFramePreparer(), value = response();
    const original = prepare(scope, value, 1);
    for (const key of ["organizationId", "projectId", "layerId", "sourceId", "contentRevision", "schemaRevision"] as const) {
      expect(prepare({ ...scope, [key]: "other" }, value, 1)).toEqual({ status: "invalid-context" });
    }
    // Actor is in the workspace cache key even though not in the response envelope.
    const otherActor = prepare({ ...scope, accountId: "other" }, value, 1);
    expect(otherActor).not.toBe(original);
    // Even the exact same object/generation is rejected if its context becomes invalid.
    value.context.geometry_included = false;
    expect(prepare(scope, value, 1)).toEqual({ status: "invalid-context" });
  });

  it("copies exact geometry and creates a fresh immutable frame on every new success generation", () => {
    const prepare = createViewportFramePreparer(), value = response();
    const original = prepare(scope, value, 1);
    if (original.status !== "ready") throw new Error("fixture invalid");
    // Mutating the upstream object cannot modify the already validated frame.
    value.items[0]!.geometry.coordinates[0] = 106;
    expect(original.features[0]!.geometry.coordinates).toEqual([105, 10]);
    // A structurally shared but refreshed authorized response is revalidated.
    const next = prepare(scope, value, 2);
    expect(next).not.toBe(original);
    expect(next).toMatchObject({ status: "ready", features: [{ geometry: { coordinates: [106, 10] } }] });
    const changedResponse = response();
    changedResponse.items[0]!.geometry.coordinates[0] = 107;
    const changed = prepare(scope, changedResponse, 2);
    expect(changed).toMatchObject({ status: "ready", features: [{ geometry: { coordinates: [107, 10] } }] });
    // Even two different payloads with the same millisecond query timestamp
    // get distinct frame versions, so the adapter cannot miss a new payload.
    if (changed.status !== "ready" || next.status !== "ready") throw new Error("fixture invalid");
    expect(changed.version).not.toBe(next.version);
  });

  it("copies line and polygon vertices exactly, rejects malformed current geometry without returning a frame", () => {
    const prepare = createViewportFramePreparer(), value = response();
    value.items = [
      { feature_id: "line", geometry: { type: "LineString", coordinates: [[105, 10], [106, 11]], coordinate_reference: crs } },
      { feature_id: "polygon", geometry: { type: "Polygon", coordinates: [[[105, 10], [106, 10], [106, 11], [105, 10]]], coordinate_reference: crs } }
    ];
    const prepared = prepare(scope, value, 1);
    if (prepared.status !== "ready") throw new Error("fixture invalid");
    expect(prepared.features.map(item => item.geometry.coordinates)).toEqual(value.items.map(item => item.geometry.coordinates));
    const malformed = response();
    malformed.items[0]!.geometry.coordinates = [181, 10];
    expect(prepare(scope, malformed, 2)).toEqual({ status: "invalid-geometry" });
    value.items[1]!.geometry = { type: "Polygon", coordinates: [[[105, 10], [106, 10], [106, 11], [105, 11]]], coordinate_reference: crs };
    expect(prepare(scope, value, 2)).toEqual({ status: "invalid-geometry" });
  });
});
