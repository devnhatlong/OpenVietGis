import type {
  MapLayerReference,
  SpatialLayer,
  SpatialLayerList
} from "@openvietgis/client-sdk";

import { currentProtectedData } from "../../app/protected-query";

/** Metadata must belong to the exact requested layer and current project. */
export function layerScopeMatches(
  layer: SpatialLayer, organizationId: string, projectId: string, layerId = layer.id
): boolean {
  return layer.id === layerId &&
    layer.organization_id === organizationId && layer.project_id === projectId &&
    layer.source.organization_id === organizationId && layer.source.project_id === projectId &&
    layer.source_id === layer.source.id;
}

export type CatalogReadState =
  | { status: "loading" | "unavailable"; page: undefined }
  | { status: "ready"; page: SpatialLayerList };

/** Never interpret pending, denied, mismatched or closed-catalog data as empty. */
export function currentAddDataCatalog(
  open: boolean,
  result: Parameters<typeof currentProtectedData<SpatialLayerList>>[0],
  organizationId: string,
  projectId: string
): CatalogReadState {
  if (!open) return { status: "loading", page: undefined };
  if (result.error !== null) return { status: "unavailable", page: undefined };
  const page = currentProtectedData(result);
  if (!page) return { status: "loading", page: undefined };
  if (page.organization_id !== organizationId ||
      page.project_id !== projectId ||
      !page.items.every(layer => layerScopeMatches(layer, organizationId, projectId))) {
    return { status: "unavailable", page: undefined };
  }
  return { status: "ready", page };
}

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
