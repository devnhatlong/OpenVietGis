import type {
  MapLayerReference,
  SpatialLayer
} from "@openvietgis/client-sdk";

export type AccessibleMapState =
  | "loading"
  | "partial"
  | "usable"
  | "empty"
  | "stale"
  | "unavailable";

export interface AccessibleMapSummary {
  projectName: string;
  mapName: string;
  activeLayerName: string | null;
  visibleLayerCount: number;
  selectedFeatureCount: number;
  focusedFeatureId: string | null;
  focusedFeatureSummary: string | null;
  state: AccessibleMapState;
  text: string;
}

const stateLabels: Record<AccessibleMapState, string> = {
  loading: "đang tải",
  stale: "cần xác thực lại",
  partial: "đang hiển thị một phần",
  usable: "sẵn sàng",
  unavailable: "không khả dụng",
  empty: "không có dữ liệu"
};

export function buildAccessibleMapSummary({
  projectName,
  references,
  metadata,
  activeLayerId,
  selectedFeatureIds,
  focusedFeatureId,
  state
}: {
  projectName: string;
  references: MapLayerReference[];
  metadata: Array<SpatialLayer | undefined>;
  activeLayerId: string | null;
  selectedFeatureIds: string[];
  focusedFeatureId: string | null;
  state: AccessibleMapState;
}): AccessibleMapSummary {
  const activeIndex = references.findIndex(
    (reference) => reference.layer_id === activeLayerId
  );
  const activeLayerName =
    activeIndex >= 0 ? metadata[activeIndex]?.name ?? null : null;
  const visibleLayerCount = references.filter(
    (reference) => reference.visible
  ).length;
  const selectedFeatureCount = selectedFeatureIds.length;
  const focusedFeatureSummary = focusedFeatureId
    ? "đang xem " + focusedFeatureId
    : null;

  const pieces = [
    "Bản đồ dự án " + projectName + ".",
    visibleLayerCount + " lớp đang hiển thị.",
    activeLayerName
      ? "Lớp hiện hành: " + activeLayerName + "."
      : "Chưa chọn lớp hiện hành.",
    selectedFeatureCount + " đối tượng đang chọn.",
    focusedFeatureId
      ? "Đang xem đối tượng " + focusedFeatureId + "."
      : null,
    "Trạng thái bản đồ: " + stateLabels[state] + "."
  ].filter(Boolean);

  return {
    projectName,
    mapName: "Bản đồ dự án",
    activeLayerName,
    visibleLayerCount,
    selectedFeatureCount,
    focusedFeatureId,
    focusedFeatureSummary,
    state,
    text: pieces.join(" ")
  };
}
