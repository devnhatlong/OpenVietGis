import { lazy, Suspense, useEffect, useState } from "react";

import { getOfficialModuleFrontend } from "../extensions/registry";

export type MapDockToolId =
  | "editing"
  | "queries"
  | "processing"
  | "cad"
  | "external"
  | "cartography"
  | "transfers"
  | "spatial"
  | "field"
  | "collab"
  | "extensions"
  | `ext:${string}`;

const EditingWorkbenchPage = lazy(() =>
  import("../platform/EditingWorkbenchPage").then((m) => ({ default: m.EditingWorkbenchPage }))
);
const QueryWorkbenchPage = lazy(() =>
  import("../platform/QueryWorkbenchPage").then((m) => ({ default: m.QueryWorkbenchPage }))
);
const ProcessingWorkbenchPage = lazy(() =>
  import("../platform/ProcessingWorkbenchPage").then((m) => ({ default: m.ProcessingWorkbenchPage }))
);
const CartographyWorkbenchPage = lazy(() =>
  import("../platform/CartographyWorkbenchPage").then((m) => ({ default: m.CartographyWorkbenchPage }))
);
const PlatformHubPage = lazy(() =>
  import("../platform/PlatformHubPage").then((m) => ({ default: m.PlatformHubPage }))
);
const ImportExportPage = lazy(() =>
  import("../transfers/ImportExportPage").then((m) => ({ default: m.ImportExportPage }))
);
const SpatialCatalogPage = lazy(() =>
  import("../spatial/SpatialCatalogPage").then((m) => ({ default: m.SpatialCatalogPage }))
);

const TOOL_TITLES: Record<string, string> = {
  editing: "Biên tập GIS (Vẽ / Sửa & Lịch sử)",
  queries: "Truy vấn Thuộc tính & Không gian",
  processing: "Phân tích Không gian (Buffer / Clip)",
  cad: "AutoCAD 2D (DXF) & Trắc địa COGO",
  external: "Tích hợp Bên thứ 3 (WMS / WMTS / COG / WFS)",
  cartography: "Trình bày & In Bản đồ PDF",
  transfers: "Nhập / Xuất Dữ liệu (GeoJSON / GPKG / SHP)",
  spatial: "Danh mục Lớp & Hệ tọa độ CRS",
  field: "Thực địa & Đồng bộ Ngoại tuyến",
  collab: "Cộng tác Nhóm & Phê duyệt",
  extensions: "Quản lý Plugin & Mô-đun Mở rộng"
};

export interface ActiveModuleSummary {
  extensionKey: string;
  label: string;
}

interface MapToolDockProps {
  tool: MapDockToolId;
  organizationId: string;
  projectId: string;
  activeModules: ActiveModuleSummary[];
  onClose: () => void;
}

export function MapToolDock({
  tool,
  organizationId,
  projectId,
  activeModules,
  onClose
}: MapToolDockProps) {
  const [wide, setWide] = useState(tool.startsWith("ext:") || tool === "editing" || tool === "cartography");

  useEffect(() => {
    setWide(tool.startsWith("ext:") || tool === "editing" || tool === "cartography");
  }, [tool]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const extKey = tool.startsWith("ext:") ? tool.slice(4) : null;
  const matchedModule = extKey ? activeModules.find((m) => m.extensionKey === extKey) : null;
  const title = extKey
    ? matchedModule?.label ?? `Mô-đun: ${extKey}`
    : TOOL_TITLES[tool] ?? "Công cụ GIS";

  function renderContent() {
    if (extKey) {
      const frontend = getOfficialModuleFrontend(extKey);
      if (!frontend) {
        return (
          <div className="gis-dock-empty">
            <strong>Không tìm thấy giao diện mô-đun ({extKey})</strong>
            <p>Hãy kiểm tra trạng thái kích hoạt trong mục Quản lý Plugin.</p>
          </div>
        );
      }
      const ModuleComponent = frontend.Component;
      return <ModuleComponent organizationId={organizationId} projectId={projectId} />;
    }

    switch (tool) {
      case "editing":
        return <EditingWorkbenchPage />;
      case "queries":
        return <QueryWorkbenchPage />;
      case "processing":
        return <ProcessingWorkbenchPage />;
      case "cartography":
        return <CartographyWorkbenchPage />;
      case "cad":
        return <PlatformHubPage embeddedTab="cad" />;
      case "external":
        return <PlatformHubPage embeddedTab="external" />;
      case "field":
        return <PlatformHubPage embeddedTab="field" />;
      case "collab":
        return <PlatformHubPage embeddedTab="collab" />;
      case "extensions":
        return <PlatformHubPage embeddedTab="extensions" />;
      case "transfers":
        return <ImportExportPage />;
      case "spatial":
        return <SpatialCatalogPage />;
      default:
        return null;
    }
  }

  return (
    <aside
      className={wide ? "gis-tool-dock is-wide" : "gis-tool-dock"}
      aria-label={title}
      data-testid="map-tool-dock"
      data-tool={tool}
    >
      <header className="gis-tool-dock-head">
        <div className="gis-tool-dock-title">
          <span className="gis-dock-dot" aria-hidden="true" />
          <strong>{title}</strong>
        </div>
        <div className="gis-tool-dock-actions">
          <button
            type="button"
            onClick={() => setWide((v) => !v)}
            title={wide ? "Thu hẹp bảng công cụ" : "Mở rộng bảng công cụ"}
          >
            {wide ? "⇔ Thu gọn" : "⇔ Mở rộng"}
          </button>
          <button
            type="button"
            className="is-close"
            onClick={onClose}
            aria-label="Đóng bảng công cụ"
            title="Đóng (Esc)"
          >
            ✕
          </button>
        </div>
      </header>
      <div className="gis-tool-dock-body">
        <Suspense fallback={<div className="gis-dock-loading">Đang mở công cụ trên bản đồ…</div>}>
          {renderContent()}
        </Suspense>
      </div>
    </aside>
  );
}
