import { describe, expect, it } from "vitest";

import type {
  MapLayerReference,
  SpatialLayer
} from "@openvietgis/client-sdk";
import { buildAccessibleMapSummary } from "./accessibility-summary";

const references: MapLayerReference[] = [
  {
    layer_id: "layer-a",
    visible: true,
    style: { color: "#123456", opacity: 1, width: 2, radius: 5 }
  },
  {
    layer_id: "layer-b",
    visible: false,
    style: { color: "#654321", opacity: 1, width: 2, radius: 5 }
  }
];

const metadata = [
  { id: "layer-a", name: "Điểm địa danh" } as SpatialLayer,
  { id: "layer-b", name: "Ranh giới" } as SpatialLayer
];

describe("accessible map summary", () => {
  it("summarizes project, active layer, visible and selected counts", () => {
    const summary = buildAccessibleMapSummary({
      projectName: "Bản đồ Hà Nội",
      references,
      metadata,
      activeLayerId: "layer-a",
      selectedFeatureIds: ["f-1", "f-2"],
      focusedFeatureId: "f-2",
      state: "partial"
    });

    expect(summary).toMatchObject({
      projectName: "Bản đồ Hà Nội",
      activeLayerName: "Điểm địa danh",
      visibleLayerCount: 1,
      selectedFeatureCount: 2,
      focusedFeatureSummary: "đang xem f-2",
      state: "partial"
    });
    expect(summary.text).toContain("1 lớp đang hiển thị");
    expect(summary.text).toContain("2 đối tượng đang chọn");
    expect(summary.text).toContain("đang hiển thị một phần");
  });

  it("handles missing active/focused data without inventing details", () => {
    const summary = buildAccessibleMapSummary({
      projectName: "Dự án trống",
      references: [],
      metadata: [],
      activeLayerId: null,
      selectedFeatureIds: [],
      focusedFeatureId: null,
      state: "empty"
    });

    expect(summary.activeLayerName).toBeNull();
    expect(summary.focusedFeatureSummary).toBeNull();
    expect(summary.text).toContain("Chưa chọn lớp hiện hành");
    expect(summary.text).toContain("không có dữ liệu");
  });

  it("does not expose hidden layer names as the active layer", () => {
    const summary = buildAccessibleMapSummary({
      projectName: "Dự án",
      references,
      metadata,
      activeLayerId: "missing",
      selectedFeatureIds: [],
      focusedFeatureId: null,
      state: "usable"
    });

    expect(summary.activeLayerName).toBeNull();
  });
});
