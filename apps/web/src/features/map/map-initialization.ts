import type { MapViewpoint } from "@openvietgis/client-sdk";
import type { Bounds } from "./workspace";

/** The engine can publish an identical camera during construction, resize and idle. */
export function sameCamera(a: MapViewpoint, b: MapViewpoint): boolean {
  return a.longitude === b.longitude &&
    a.latitude === b.latitude &&
    a.zoom === b.zoom &&
    a.bearing === b.bearing &&
    a.pitch === b.pitch &&
    a.crs === b.crs;
}

export function sameViewportBounds(a: Bounds | null, b: Bounds): boolean {
  // Maintain the existing tiny floating-point jitter tolerance; never invent
  // bounds, quantize to tiles, or substitute an estimated camera projection.
  return a !== null && a.every((value, index) => Math.abs(value - b[index]!) < 1e-9);
}
