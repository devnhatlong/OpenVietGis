import type { ActiveModuleSummary, MapDockToolId } from "./MapToolDock";

interface MapActivityRailProps {
  leftOpen: boolean;
  activeTool: MapDockToolId | null;
  activeModules: ActiveModuleSummary[];
  onToggleLeft: () => void;
  onSelectTool: (tool: MapDockToolId | null) => void;
}

const RAIL_ITEMS: Array<{ id: MapDockToolId; label: string; title: string }> = [
  { id: "editing", label: "Biên tập", title: "Biên tập GIS (Vẽ / Sửa hình học)" },
  { id: "queries", label: "Truy vấn", title: "Truy vấn Thuộc tính & Không gian" },
  { id: "processing", label: "Phân tích", title: "Phân tích Buffer / Clip" },
  { id: "cad", label: "CAD", title: "AutoCAD 2D DXF & COGO" },
  { id: "external", label: "WMS", title: "Tích hợp Bên thứ 3 (WMS / WMTS / COG)" },
  { id: "cartography", label: "In ấn", title: "Trình bày & In Bản đồ PDF" },
  { id: "transfers", label: "Nhập/Xuất", title: "Nhập / Xuất dữ liệu GIS" },
  { id: "spatial", label: "CRS", title: "Danh mục Lớp & Hệ tọa độ CRS" },
  { id: "field", label: "Thực địa", title: "Thực địa & Đồng bộ Offline" },
  { id: "extensions", label: "Plugin", title: "Quản lý Plugin & Mô-đun" }
];

function RailIcon({ id }: { id: string }) {
  const p = {
    width: 17,
    height: 17,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.9,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const
  };
  switch (id) {
    case "layers":
      return <svg {...p}><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 12 12 17 22 12" /><polyline points="2 17 12 22 22 17" /></svg>;
    case "editing":
      return <svg {...p}><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" /></svg>;
    case "queries":
      return <svg {...p}><circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" /></svg>;
    case "processing":
      return <svg {...p}><circle cx="9" cy="12" r="6" /><circle cx="15" cy="12" r="6" /></svg>;
    case "cad":
      return <svg {...p}><path d="M12 3 2 21h20L12 3Z" /><path d="M12 10v7" /></svg>;
    case "external":
      return <svg {...p}><circle cx="12" cy="12" r="9" /><path d="M3 12h18" /><path d="M12 3a14 14 0 0 1 0 18" /></svg>;
    case "cartography":
      return <svg {...p}><polyline points="6 9 6 2 18 2 18 9" /><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" /><rect x="6" y="14" width="12" height="8" /></svg>;
    case "transfers":
      return <svg {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>;
    case "spatial":
      return <svg {...p}><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M3 5v14a9 3 0 0 0 18 0V5" /></svg>;
    case "field":
      return <svg {...p}><rect x="5" y="2" width="14" height="20" rx="2" /><line x1="12" y1="18" x2="12.01" y2="18" /></svg>;
    case "extensions":
      return <svg {...p}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /></svg>;
    default:
      return <svg {...p}><path d="M3 10.5 12 3l9 7.5" /><path d="M5 9.5V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9.5" /></svg>;
  }
}

export function MapActivityRail({
  leftOpen,
  activeTool,
  activeModules,
  onToggleLeft,
  onSelectTool
}: MapActivityRailProps) {
  return (
    <aside className="gis-activity-rail" aria-label="Thanh công cụ GIS dọc">
      <button
        type="button"
        className={leftOpen ? "gis-rail-btn is-active" : "gis-rail-btn"}
        title="Bật / Tắt bảng Lớp dữ liệu"
        aria-pressed={leftOpen}
        onClick={onToggleLeft}
      >
        <RailIcon id="layers" />
        <span>Lớp</span>
      </button>

      <div className="gis-rail-sep" aria-hidden="true" />

      {activeModules.map((mod) => {
        const id: MapDockToolId = `ext:${mod.extensionKey}`;
        const active = activeTool === id;
        return (
          <button
            key={mod.extensionKey}
            type="button"
            className={active ? "gis-rail-btn is-module is-active" : "gis-rail-btn is-module"}
            title={mod.label}
            aria-pressed={active}
            onClick={() => onSelectTool(active ? null : id)}
          >
            <RailIcon id="module" />
            <span>{mod.label}</span>
          </button>
        );
      })}

      {RAIL_ITEMS.map((item) => {
        const active = activeTool === item.id;
        return (
          <button
            key={item.id}
            type="button"
            className={active ? "gis-rail-btn is-active" : "gis-rail-btn"}
            title={item.title}
            aria-pressed={active}
            onClick={() => onSelectTool(active ? null : item.id)}
          >
            <RailIcon id={item.id} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </aside>
  );
}
