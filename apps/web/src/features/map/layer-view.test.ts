import { describe, expect, it } from "vitest";

import type {
  MapLayerReference,
  SpatialLayer
} from "@openvietgis/client-sdk";
import { buildLayerPanelItemView } from "./layer-view";

const ref: MapLayerReference = {
  layer_id: "layer-1",
  visible: true,
  style: { color: "#123456", opacity: 1, width: 2, radius: 5 }
};

function layerWith(
  overrides: Partial<SpatialLayer["capabilities"][number]> = {}
): SpatialLayer {
  return {
    id: "layer-1",
    organization_id: "org-1",
    project_id: "project-1",
    source_id: "source-1",
    name: "Điểm thử nghiệm",
    lifecycle: "active",
    source: {
      id: "source-1",
      organization_id: "org-1",
      project_id: "project-1",
      name: "Nguồn thử nghiệm",
      lifecycle: "active"
    },
    capabilities: [
      {
        name: "render",
        technical_supported: true,
        available: true,
        actor_authorized: true,
        required_permission: "project.read",
        ...overrides
      }
    ]
  } as SpatialLayer;
}

describe("layer panel view", () => {
  it("distinguishes permission denial from unsupported capability", () => {
    expect(
      buildLayerPanelItemView(
        ref,
        layerWith({ actor_authorized: false }),
        "usable",
        null,
        0,
        1
      ).availability
    ).toBe("permission");

    expect(
      buildLayerPanelItemView(
        ref,
        layerWith({ technical_supported: false }),
        "usable",
        null,
        0,
        1
      ).availability
    ).toBe("unsupported");
  });

  it("preserves partial and stale states explicitly", () => {
    expect(
      buildLayerPanelItemView(ref, layerWith(), "partial — bounded", "layer-1", 0, 2)
        .availability
    ).toBe("partial");
    expect(
      buildLayerPanelItemView(ref, layerWith(), "stale — revalidation required", null, 1, 2)
        .availability
    ).toBe("stale");
  });

  it("distinguishes viewport loading and empty from a usable layer", () => {
    expect(buildLayerPanelItemView(ref, layerWith(), "loading", null, 0, 1))
      .toMatchObject({ availability: "loading", availabilityLabel: "Đang tải dữ liệu", canZoom: true });
    expect(buildLayerPanelItemView(ref, layerWith(), "empty", null, 0, 1))
      .toMatchObject({ availability: "empty", availabilityLabel: "Không có đối tượng trong khung nhìn", canZoom: true });
  });

  it("exposes stable order and non-drag command availability", () => {
    const item = buildLayerPanelItemView(ref, layerWith(), "usable", "layer-1", 1, 3);
    expect(item.name).toBe("Điểm thử nghiệm");
    expect(item.active).toBe(true);
    expect(item.canMoveUp).toBe(true);
    expect(item.canMoveDown).toBe(true);
    expect(item.canZoom).toBe(true);
  });
});
