import { useEffect, useMemo, useRef, useState } from "react";

import { invokeCommand, type MapCommand } from "./commands";
import type { ActiveModuleSummary, MapDockToolId } from "./MapToolDock";

interface CadCommandItem {
  id: string;
  alias: string;
  keywords: string;
  label: string;
  group: string;
  enabled: boolean;
  reason: string | null;
  run: () => void;
}

interface MapCommandLineProps {
  commands: MapCommand[];
  activeModules: ActiveModuleSummary[];
  visible: boolean;
  onSelectTool: (tool: MapDockToolId | null) => void;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onToggleTable: () => void;
  onOpenTechnical: () => void;
  onReloadShared: () => void;
  onHide: () => void;
}

const MAP_COMMAND_ALIASES: Record<string, { alias: string; keywords: string }> = {
  "map.add-data": { alias: "ADD", keywords: "add data them du lieu layer" },
  "map.fit-layer": { alias: "ZL", keywords: "zl zoom layer thu phong lop" },
  "map.fit-all": { alias: "ZE", keywords: "ze zoom extents toan bo ban do" },
  "map.fit-selection": { alias: "ZS", keywords: "zs zoom selection vung chon" },
  "map.clear-selection": { alias: "CLR", keywords: "clr clear bo chon unselect" },
  "map.save": { alias: "SAVE", keywords: "save qsave luu ban do" },
  "map.set-default-viewpoint": { alias: "VIEW", keywords: "view home goc nhin mac dinh" },
  "map.clear-default-viewpoint": { alias: "VIEWCLR", keywords: "xoa goc nhin mac dinh" },
  "map.zoom-in": { alias: "ZI", keywords: "zi zoom in phong to +" },
  "map.zoom-out": { alias: "ZO", keywords: "zo zoom out thu nho -" }
};

export function MapCommandLine({
  commands,
  activeModules,
  visible,
  onSelectTool,
  onToggleLeft,
  onToggleRight,
  onToggleTable,
  onOpenTechnical,
  onReloadShared,
  onHide
}: MapCommandLineProps) {
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [history, setHistory] = useState<string[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  const allItems = useMemo<CadCommandItem[]>(() => {
    const mapItems: CadCommandItem[] = commands.map((c) => {
      const meta = MAP_COMMAND_ALIASES[c.id];
      return {
        id: c.id,
        alias: meta?.alias ?? c.id.replace(/^map\./, "").toUpperCase(),
        keywords: `${meta?.keywords ?? ""} ${c.label}`.toLowerCase(),
        label: c.label,
        group: "Bản đồ",
        enabled: c.enabled,
        reason: c.reason,
        run: () => {
          invokeCommand(commands, c.id, "search");
        }
      };
    });

    const dockItems: CadCommandItem[] = [
      { id: "tool.cad", alias: "CAD", keywords: "cad dxf cogo autocad vn2000", label: "AutoCAD 2D (DXF) & Trắc địa COGO", group: "CAD / GIS", enabled: true, reason: null, run: () => onSelectTool("cad") },
      { id: "tool.editing", alias: "EDIT", keywords: "edit draw bien tap ve sua hinh hoc", label: "Biên tập GIS (Vẽ / Sửa & Lịch sử)", group: "CAD / GIS", enabled: true, reason: null, run: () => onSelectTool("editing") },
      { id: "tool.queries", alias: "Q", keywords: "q query truy van loc thuoc tinh", label: "Truy vấn Thuộc tính & Không gian", group: "CAD / GIS", enabled: true, reason: null, run: () => onSelectTool("queries") },
      { id: "tool.processing", alias: "BUF", keywords: "buf clip buffer phan tich geoprocessing", label: "Phân tích Không gian (Buffer / Clip)", group: "CAD / GIS", enabled: true, reason: null, run: () => onSelectTool("processing") },
      { id: "tool.external", alias: "WMS", keywords: "wms wmts cog wfs tich hop ben thu 3", label: "Tích hợp Bên thứ 3 (WMS / WMTS / COG)", group: "Dữ liệu", enabled: true, reason: null, run: () => onSelectTool("external") },
      { id: "tool.transfers", alias: "IMP", keywords: "imp exp import export nhap xuat geojson gpkg", label: "Nhập / Xuất dữ liệu (GeoJSON / GPKG)", group: "Dữ liệu", enabled: true, reason: null, run: () => onSelectTool("transfers") },
      { id: "tool.spatial", alias: "CRS", keywords: "crs catalog danh muc lop he toa do", label: "Danh mục Lớp & Hệ tọa độ CRS", group: "Dữ liệu", enabled: true, reason: null, run: () => onSelectTool("spatial") },
      { id: "tool.cartography", alias: "PLOT", keywords: "plot print in an ban do pdf", label: "Trình bày & In Bản đồ PDF", group: "Xuất bản", enabled: true, reason: null, run: () => onSelectTool("cartography") },
      { id: "tool.field", alias: "FIELD", keywords: "field offline thuc dia dong bo", label: "Thực địa & Đồng bộ Ngoại tuyến", group: "Mở rộng", enabled: true, reason: null, run: () => onSelectTool("field") },
      { id: "tool.extensions", alias: "PLUGIN", keywords: "plugin module mo dun mo rong", label: "Quản lý Plugin & Mô-đun Mở rộng", group: "Mở rộng", enabled: true, reason: null, run: () => onSelectTool("extensions") },
      { id: "ui.layers", alias: "LA", keywords: "la layer lop du lieu", label: "Bật / Tắt bảng Lớp dữ liệu", group: "Giao diện", enabled: true, reason: null, run: onToggleLeft },
      { id: "ui.table", alias: "ATTR", keywords: "attr table bang thuoc tinh", label: "Bật / Tắt Bảng thuộc tính", group: "Giao diện", enabled: true, reason: null, run: onToggleTable },
      { id: "ui.inspector", alias: "PROP", keywords: "prop info chi tiet doi tuong", label: "Bật / Tắt Chi tiết đối tượng", group: "Giao diện", enabled: true, reason: null, run: onToggleRight },
      { id: "ui.tech", alias: "TECH", keywords: "tech ky thuat crs thong tin", label: "Thông tin kỹ thuật & CRS", group: "Hệ thống", enabled: true, reason: null, run: onOpenTechnical },
      { id: "ui.reload", alias: "RELOAD", keywords: "reload tai lai ban do chung", label: "Tải lại bản đồ chung", group: "Hệ thống", enabled: true, reason: null, run: onReloadShared },
      { id: "ui.close-dock", alias: "CLOSE", keywords: "close dong bang cong cu", label: "Đóng bảng công cụ đang mở", group: "Giao diện", enabled: true, reason: null, run: () => onSelectTool(null) }
    ];

    const moduleItems: CadCommandItem[] = activeModules.map((mod) => ({
      id: `ext:${mod.extensionKey}`,
      alias: mod.extensionKey.slice(0, 6).toUpperCase(),
      keywords: `${mod.extensionKey} ${mod.label}`.toLowerCase(),
      label: `Mở mô-đun: ${mod.label}`,
      group: "Mô-đun",
      enabled: true,
      reason: null,
      run: () => onSelectTool(`ext:${mod.extensionKey}`)
    }));

    return [...dockItems, ...moduleItems, ...mapItems];
  }, [
    commands,
    activeModules,
    onSelectTool,
    onToggleLeft,
    onToggleRight,
    onToggleTable,
    onOpenTechnical,
    onReloadShared
  ]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return allItems;
    return allItems
      .filter(
        (item) =>
          item.alias.toLowerCase().includes(q) ||
          item.label.toLowerCase().includes(q) ||
          item.keywords.includes(q)
      )
      .sort((a, b) => {
        const aExact = a.alias.toLowerCase() === q ? 0 : a.alias.toLowerCase().startsWith(q) ? 1 : 2;
        const bExact = b.alias.toLowerCase() === q ? 0 : b.alias.toLowerCase().startsWith(q) ? 1 : 2;
        return aExact - bExact;
      });
  }, [allItems, query]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  // Global '/' shortcut to focus AutoCAD command bar (when not typing inside another input)
  useEffect(() => {
    if (!visible) return;
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const inInput =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);
      if (!inInput && event.key === "/") {
        event.preventDefault();
        inputRef.current?.focus();
        setFocused(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [visible]);

  // Close autocomplete popup on outside click
  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setFocused(false);
        setShowHistory(false);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, []);

  function runItem(item: CadCommandItem) {
    if (!item.enabled) {
      setHistory((prev) => [`${item.alias} — ${item.reason ?? "Không khả dụng"}`, ...prev].slice(0, 12));
      return;
    }
    item.run();
    setHistory((prev) => [`${item.alias} → ${item.label}`, ...prev].slice(0, 12));
    setQuery("");
    setFocused(false);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelectedIndex((i) => Math.min(filtered.length - 1, i + 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelectedIndex((i) => Math.max(0, i - 1));
    } else if (event.key === "Enter" || event.key === "Tab") {
      if (filtered.length > 0) {
        event.preventDefault();
        const picked = filtered[selectedIndex] ?? filtered[0];
        if (picked) runItem(picked);
      }
    } else if (event.key === "Escape") {
      event.preventDefault();
      setQuery("");
      setFocused(false);
      inputRef.current?.blur();
    }
  }

  if (!visible) return null;

  const popupOpen = focused && filtered.length > 0;
  const lastLog = history[0] ?? null;

  return (
    <div ref={rootRef} className="acad-cmdline-wrap" data-testid="acad-command-line">
      {showHistory && history.length > 0 ? (
        <div className="acad-history-panel" role="log" aria-label="Lịch sử lệnh">
          <div className="acad-popup-head">
            <span>Lịch sử lệnh gần đây</span>
            <button type="button" onClick={() => setHistory([])}>Xóa</button>
          </div>
          <ul>
            {history.map((line, idx) => (
              <li key={idx}><code>❯ {line}</code></li>
            ))}
          </ul>
        </div>
      ) : null}

      {popupOpen ? (
        <div className="acad-autocomplete" role="listbox" aria-label="Gợi ý lệnh AutoCAD / GIS">
          <div className="acad-popup-head">
            <span>Lệnh khả dụng ({filtered.length})</span>
            <span>↑↓ chọn · Enter chạy · Esc hủy</span>
          </div>
          <ul>
            {filtered.slice(0, 12).map((item, idx) => (
              <li key={item.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={idx === selectedIndex}
                  disabled={!item.enabled}
                  className={idx === selectedIndex ? "is-selected" : undefined}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    runItem(item);
                  }}
                >
                  <kbd className="acad-alias">{item.alias}</kbd>
                  <span className="acad-label">
                    {item.label}
                    {!item.enabled && item.reason ? <small>{item.reason}</small> : null}
                  </span>
                  <span className="acad-group">{item.group}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {lastLog && !popupOpen && !showHistory ? (
        <div className="acad-last-echo" aria-live="polite">
          <span>❯ {lastLog}</span>
        </div>
      ) : null}

      <div className={focused ? "acad-cmdline is-focused" : "acad-cmdline"}>
        <span className="acad-grip" aria-hidden="true">⋮⋮</span>
        <span className="acad-prompt">LỆNH ❯</span>
        <input
          ref={inputRef}
          type="text"
          value={query}
          aria-label="Nhập lệnh bản đồ"
          placeholder="Nhập lệnh (ZE, CAD, EDIT, WMS, ADD, SAVE, PLOT, LA, ATTR…) hoặc bấm /"
          onFocus={() => {
            setFocused(true);
            setShowHistory(false);
          }}
          onChange={(e) => {
            setQuery(e.target.value);
            setFocused(true);
          }}
          onKeyDown={handleKeyDown}
        />
        <button
          type="button"
          className="acad-bar-btn"
          title="Lịch sử lệnh"
          onClick={() => {
            setShowHistory((v) => !v);
            setFocused(false);
          }}
        >
          ▲
        </button>
        <button
          type="button"
          className="acad-bar-btn"
          title="Ẩn dòng lệnh"
          aria-label="Ẩn dòng lệnh"
          onClick={onHide}
        >
          ✕
        </button>
      </div>
    </div>
  );
}
