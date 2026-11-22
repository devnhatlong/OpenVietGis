import type { MapStyle, MapViewpoint } from "@openvietgis/client-sdk";
import type { Bounds } from "./workspace";

export type BasemapId = "grid" | "osm" | "satellite" | "hybrid" | "google-satellite" | "google-hybrid" | "topo" | "dark";

export interface BasemapOption {
  id: BasemapId;
  label: string;
  available: boolean;
}

// The accepted shared configuration currently allows only grid. HTTPS is not
// permission to disclose viewed geography. Online providers must remain
// disabled until an approved/licensed configuration and informed opt-in exist.
export const LOCAL_BASEMAP = "grid" as const;
export const ONLINE_BASEMAP_UNAVAILABLE = "Nền trực tuyến chưa được cấu hình/phê duyệt; lưới cục bộ không gửi vị trí khung nhìn ra ngoài.";
const httpsLive = typeof window !== "undefined" && window.location?.protocol === "https:";

export const BASEMAP_OPTIONS: BasemapOption[] = [
  { id: "grid", label: "Lưới tọa độ (Ngoại tuyến)", available: true },
  { id: "google-hybrid", label: "Google Hybrid (Vệ tinh + Nhãn)", available: httpsLive },
  { id: "google-satellite", label: "Vệ tinh Google", available: httpsLive },
  { id: "hybrid", label: "Vệ tinh Esri + Nhãn", available: httpsLive },
  { id: "satellite", label: "Vệ tinh Esri", available: httpsLive },
  { id: "osm", label: "Đường phố (OSM)", available: httpsLive },
  { id: "topo", label: "Địa hình (Topo)", available: httpsLive },
  { id: "dark", label: "Nền tối", available: httpsLive }
];

export function isBasemapAvailable(id: BasemapId): boolean {
  return id === LOCAL_BASEMAP || httpsLive;
}

export interface RenderGeometry {
  type: "Point" | "LineString" | "Polygon";
  coordinates: unknown;
}
export interface RenderFeature {
  feature_id: string;
  geometry: RenderGeometry;
}
export interface RenderLayer {
  id: string;
  /** Current actor/tenant/layer/source/revision pin, retained only in the adapter. */
  scopeKey: string;
  style: MapStyle;
  features: readonly RenderFeature[];
}
export interface MapEngineEvents {
  viewport: (bounds: Bounds, camera: MapViewpoint) => void;
  pick: (id: string, multiple: boolean) => void;
  ready: (ready: boolean) => void;
  error: () => void;
}
export interface MapEngine {
  setBasemap(id: BasemapId): void;
  setLayers(layers: RenderLayer[]): void;
  setActiveLayer(id: string | null): void;
  setSelection(layerId: string | null, ids: string[]): void;
  setCamera(camera: MapViewpoint): void;
  getCamera(): MapViewpoint;
  fitBounds(bounds: Bounds): void;
  zoom(delta: number): void;
  clear(): void;
  destroy(): void;
}
