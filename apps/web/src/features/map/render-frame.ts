import type { MapViewport } from "@openvietgis/client-sdk";
import type { RenderFeature, RenderGeometry } from "./engine";
import { selectionKey, viewportMatches, type SelectionScope } from "./workspace";

type PreparedViewport =
  | { status: "ready"; features: readonly RenderFeature[]; version: number }
  | { status: "invalid-context" }
  | { status: "invalid-geometry" };

// Only arrays prepared and deeply frozen by this module are eligible for the
// renderer's same-object validation/signature fast path. External input still
// goes through independent adapter validation on every application.
const immutableFeatures = new WeakSet<readonly RenderFeature[]>();

export function isImmutableViewportFeatures(features: readonly RenderFeature[]): boolean {
  return immutableFeatures.has(features);
}

function position(value: unknown): readonly number[] {
  if (!Array.isArray(value) || value.length !== 2) throw new Error("Invalid display position");
  const [x, y] = value;
  if (typeof x !== "number" || typeof y !== "number" || !Number.isFinite(x) || !Number.isFinite(y) ||
      x < -180 || x > 180 || y < -85.05112878 || y > 85.05112878)
    throw new Error("Unsupported display coordinate");
  return Object.freeze([x, y]);
}

function line(value: unknown, minimum: number): readonly (readonly number[])[] {
  if (!Array.isArray(value) || value.length < minimum) throw new Error("Invalid display line");
  return Object.freeze(value.map(position));
}

function coordinates(type: RenderGeometry["type"], value: unknown): unknown {
  if (type === "Point") return position(value);
  if (type === "LineString") return line(value, 2);
  if (!Array.isArray(value) || !value.length) throw new Error("Invalid display polygon");
  return Object.freeze(value.map(ring => {
    const copied = line(ring, 4);
    const first = copied[0]!, last = copied[copied.length - 1]!;
    if (first[0] !== last[0] || first[1] !== last[1]) throw new Error("Open polygon ring");
    return copied;
  }));
}

/**
 * Local to one Workspace instance. This is a CPU/allocation cache, not an
 * authorization cache: callers MUST supply only a currentProtectedData value.
 * Recheck its exact response context on every call, and reuse geometry only
 * within the same React Query success generation and actor/tenant/source pins.
 * A refetch (even with structurally shared data) triggers fresh preparation.
 */
export function createViewportFramePreparer() {
  const cache = new WeakMap<MapViewport, { scope: string; generation: number; result: PreparedViewport }>();
  let version = 0;

  return (scope: SelectionScope, value: MapViewport, generation: number): PreparedViewport => {
    if (!viewportMatches(scope, value.context)) return { status: "invalid-context" };
    const key = selectionKey(scope);
    const existing = cache.get(value);
    if (existing?.scope === key && existing.generation === generation) return existing.result;

    let result: PreparedViewport;
    try {
      const features = Object.freeze(value.items.map(item => {
        const geometry = item.geometry;
        if (!geometry || geometry.coordinate_reference?.code !== 4326 ||
            !["Point", "LineString", "Polygon"].includes(geometry.type))
          throw new Error("Invalid display geometry");
        // Copy and validate coordinates together; the cache doesn't freeze or
        // mutate the API response and cannot retain mutable source geometry.
        return Object.freeze({
          feature_id: item.feature_id,
          geometry: Object.freeze({ type: geometry.type, coordinates: coordinates(geometry.type, geometry.coordinates) })
        });
      }));
      immutableFeatures.add(features);
      result = { status: "ready", features, version: ++version };
    } catch {
      result = { status: "invalid-geometry" };
    }
    cache.set(value, { scope: key, generation, result });
    return result;
  };
}
