import type {
  ProjectMap,
  SpatialLayer
} from "@openvietgis/client-sdk";

export interface TechnicalCapabilityView {
  name: string;
  status: "ready" | "permission" | "unsupported" | "unavailable";
  label: string;
}

export interface TechnicalLayerView {
  layerId: string;
  sourceId: string;
  contentRevision: string;
  schemaRevision: string;
  sourceCrs: string;
  storedCrs: string;
  capabilities: TechnicalCapabilityView[];
}

export interface TechnicalDetailsView {
  organizationId: string;
  projectId: string;
  mapId: string;
  configurationRevision: number;
  activeLayer: TechnicalLayerView | null;
}

function crsLabel(
  value: { authority?: string; code?: number } | null | undefined
): string {
  if (!value?.code) return "Chưa xác định";
  return (value.authority ?? "EPSG") + ":" + value.code;
}

function capabilityStatus(
  capability: SpatialLayer["capabilities"][number]
): TechnicalCapabilityView {
  if (!capability.technical_supported) {
    return {
      name: capability.name,
      status: "unsupported",
      label: "Không hỗ trợ kỹ thuật"
    };
  }
  if (!capability.actor_authorized) {
    return {
      name: capability.name,
      status: "permission",
      label: "Không đủ quyền"
    };
  }
  if (!capability.available) {
    return {
      name: capability.name,
      status: "unavailable",
      label: "Không khả dụng"
    };
  }
  return {
    name: capability.name,
    status: "ready",
    label: "Sẵn sàng"
  };
}

export function buildTechnicalDetailsView({
  organizationId,
  projectId,
  map,
  activeLayer
}: {
  organizationId: string;
  projectId: string;
  map: ProjectMap;
  activeLayer: SpatialLayer | undefined;
}): TechnicalDetailsView {
  return {
    organizationId,
    projectId,
    mapId: map.map_id,
    configurationRevision: map.configuration_revision,
    activeLayer: activeLayer
      ? {
          layerId: activeLayer.id,
          sourceId: activeLayer.source_id,
          contentRevision: activeLayer.source.content_revision,
          schemaRevision: activeLayer.source.schema_revision,
          sourceCrs: crsLabel(activeLayer.source.source_crs),
          storedCrs: crsLabel(activeLayer.source.stored_crs),
          capabilities: activeLayer.capabilities.map(capabilityStatus)
        }
      : null
  };
}
