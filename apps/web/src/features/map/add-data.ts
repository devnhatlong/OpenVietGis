import type {
  MapLayerReference,
  SpatialLayer
} from "@openvietgis/client-sdk";

export type AddDataAvailability =
  | "addable"
  | "already-present"
  | "permission"
  | "unsupported"
  | "unavailable";

export interface AddDataCandidateView {
  layerId: string;
  name: string;
  geometryFamily: string;
  crsLabel: string;
  alreadyOnMap: boolean;
  addable: boolean;
  availability: AddDataAvailability;
  reason: string | null;
}

function candidateAvailability(
  layer: SpatialLayer,
  alreadyOnMap: boolean
): Pick<
  AddDataCandidateView,
  "addable" | "availability" | "reason"
> {
  if (alreadyOnMap) {
    return {
      addable: false,
      availability: "already-present",
      reason: "Lớp này đã có trên bản đồ."
    };
  }

  const render = layer.capabilities.find((item) => item.name === "render");
  if (!render || !render.technical_supported) {
    return {
      addable: false,
      availability: "unsupported",
      reason: "Kiểu dữ liệu hoặc hệ tọa độ chưa được hỗ trợ để hiển thị."
    };
  }
  if (!render.actor_authorized) {
    return {
      addable: false,
      availability: "permission",
      reason: "Tài khoản hiện tại không có quyền hiển thị lớp này."
    };
  }
  if (
    !render.available ||
    layer.lifecycle !== "active" ||
    layer.source.lifecycle !== "active"
  ) {
    return {
      addable: false,
      availability: "unavailable",
      reason: "Nguồn hoặc lớp hiện chưa sẵn sàng."
    };
  }

  return {
    addable: true,
    availability: "addable",
    reason: null
  };
}

export function buildAddDataCandidates(
  catalog: SpatialLayer[],
  references: MapLayerReference[]
): AddDataCandidateView[] {
  const current = new Set(references.map((item) => item.layer_id));
  return catalog.map((layer) => {
    const alreadyOnMap = current.has(layer.id);
    return {
      layerId: layer.id,
      name: layer.name,
      geometryFamily: layer.source.schema.geometry_family,
      crsLabel: layer.source.stored_crs
        ? "EPSG:" + layer.source.stored_crs.code
        : "CRS chưa xác định",
      alreadyOnMap,
      ...candidateAvailability(layer, alreadyOnMap)
    };
  });
}
