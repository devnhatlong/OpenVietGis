import { describe, expect, it } from "vitest";
import type { MapViewpoint } from "@openvietgis/client-sdk";
import { sameCamera, sameViewportBounds } from "./map-initialization";

const camera: MapViewpoint = {
  longitude: 105.81,
  latitude: 21.02,
  zoom: 12,
  bearing: 0,
  pitch: 0,
  crs: 4326
};

describe("exact initial camera publications", () => {
  it("suppresses duplicate camera events but not any actual camera component change", () => {
    expect(sameCamera(camera, { ...camera })).toBe(true);
    for (const key of ["longitude", "latitude", "zoom", "bearing", "pitch"] as const) {
      expect(sameCamera(camera, { ...camera, [key]: camera[key] + 1e-10 })).toBe(false);
    }
  });
  it("retains the existing viewport jitter tolerance without guessing initial bounds", () => {
    expect(sameViewportBounds(null, [0, 0, 1, 1])).toBe(false);
    expect(sameViewportBounds([0, 0, 1, 1], [0, 0, 1, 1])).toBe(true);
    expect(sameViewportBounds([0, 0, 1, 1], [0, 0, 1, 1 + 1e-10])).toBe(true);
    expect(sameViewportBounds([0, 0, 1, 1], [0, 0, 1, 1 + 1e-7])).toBe(false);
  });
});
