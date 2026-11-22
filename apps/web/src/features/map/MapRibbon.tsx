import { useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ThemeToggle } from "../../app/shell/ThemeToggle";
import { AccountMenu } from "../auth/AccountMenu";
import { invokeCommand, type MapCommand } from "./commands";
import type { ActiveModuleSummary, MapDockToolId } from "./MapToolDock";

interface MapRibbonProps {
  organizationId: string;
  projectName: string;
  revision: number;
  writable: boolean;
  archived: boolean;
  dirty: boolean;
  saveState: string;
  saveLabel: string;
  commands: MapCommand[];
  activeTool: MapDockToolId | null;
  activeModules: ActiveModuleSummary[];
  leftOpen: boolean;
  rightOpen: boolean;
  tableOpen: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onToggleTable: () => void;
  onSelectTool: (tool: MapDockToolId | null) => void;
  onOpenTechnical: () => void;
}

export function MapRibbon({
  organizationId,
  projectName,
  revision,
  dirty,
  saveState,
  saveLabel,
  commands,
  rightOpen,
  tableOpen,
  onToggleRight,
  onToggleTable,
  onOpenTechnical
}: MapRibbonProps) {
  const [search, setSearch] = useState("");
  const searchMenu = useRef<HTMLDetailsElement>(null);

  function executeSearch(id: string): void {
    if (!invokeCommand(commands, id, "search")) return;
    if (searchMenu.current) {
      searchMenu.current.open = false;
      searchMenu.current.querySelector("summary")?.focus();
    }
  }

  const addCmd = commands.find((c) => c.id === "map.add-data");
  const fitAllCmd = commands.find((c) => c.id === "map.fit-all");
  const saveCmd = commands.find((c) => c.id === "map.save");

  return (
    <header className="gis-top-menubar" data-testid="gis-ribbon">
      <div className="gis-header-left">
        <Link to="/app" className="gis-home-badge" title="Về Trang tổng quan">
          OVG
        </Link>
        <Link to={`/app/organizations/${organizationId}/projects`} className="gis-back-btn">
          ← Dự án
        </Link>
        <h1>
          {projectName}
          <small>v{revision}</small>
        </h1>
        <span
          className={
            dirty
              ? "map-context-unsaved map-status-pill"
              : "map-context-saved map-status-pill"
          }
          data-save-state={saveState}
        >
          {saveLabel}
        </span>
      </div>

      <div className="gis-header-meta">
        {addCmd ? (
          <button
            type="button"
            className="gis-top-primary"
            disabled={!addCmd.enabled}
            title={addCmd.reason ?? addCmd.label}
            onClick={() => invokeCommand(commands, addCmd.id, "toolbar")}
          >
            + Thêm dữ liệu
          </button>
        ) : null}
        {fitAllCmd ? (
          <button
            type="button"
            disabled={!fitAllCmd.enabled}
            title={fitAllCmd.reason ?? fitAllCmd.label}
            onClick={() => invokeCommand(commands, fitAllCmd.id, "toolbar")}
          >
            Toàn bản đồ
          </button>
        ) : null}
        {saveCmd ? (
          <button
            type="button"
            disabled={!saveCmd.enabled}
            title={saveCmd.reason ?? saveCmd.label}
            onClick={() => invokeCommand(commands, saveCmd.id, "toolbar")}
          >
            Lưu
          </button>
        ) : null}

        <span className="gis-top-sep" aria-hidden="true" />

        <button
          type="button"
          className={tableOpen ? "is-on" : undefined}
          onClick={onToggleTable}
        >
          Bảng thuộc tính
        </button>
        <button
          type="button"
          className={rightOpen ? "is-on" : undefined}
          onClick={onToggleRight}
        >
          Chi tiết
        </button>

        <details ref={searchMenu} className="map-command-search">
          <summary title="Tất cả lệnh bản đồ">⋯</summary>
          <label>
            Tìm lệnh bản đồ
            <input
              aria-label="Tìm lệnh bản đồ"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
          <ul>
            {commands
              .filter((c) => c.label.toLowerCase().includes(search.toLowerCase()))
              .map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    disabled={!c.enabled}
                    title={c.reason ?? c.label}
                    onClick={() => executeSearch(c.id)}
                  >
                    {c.label}
                  </button>
                  {!c.enabled ? <small>{c.reason}</small> : null}
                </li>
              ))}
            <li>
              <button type="button" onClick={onOpenTechnical}>
                Thông tin kỹ thuật & CRS
              </button>
            </li>
          </ul>
        </details>

        <ThemeToggle />
        <AccountMenu />
      </div>
    </header>
  );
}
