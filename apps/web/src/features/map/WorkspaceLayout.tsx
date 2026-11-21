import {
  useEffect,
  useMemo,
  useState,
  type CSSProperties,
  type ReactNode
} from "react";

import { ResizablePanel } from "../../ui/primitives/ResizablePanel";
import {
  getWorkspaceResponsiveMode,
  type WorkspaceResponsiveMode
} from "./responsive-mode";
import {
  WORKSPACE_LAYOUT_BOUNDS,
  type WorkspaceLayoutPreference
} from "./workspace-layout";

function currentMode(): WorkspaceResponsiveMode {
  return getWorkspaceResponsiveMode(
    typeof window === "undefined" ? 1280 : window.innerWidth
  );
}

export function WorkspaceLayout({
  preference,
  onPreferenceChange,
  left,
  map,
  right,
  bottom
}: {
  preference: WorkspaceLayoutPreference;
  onPreferenceChange: (value: WorkspaceLayoutPreference) => void;
  left: ReactNode;
  map: ReactNode;
  right: ReactNode;
  bottom: ReactNode;
}) {
  const [mode, setMode] = useState<WorkspaceResponsiveMode>(currentMode);

  useEffect(() => {
    const update = () => setMode(currentMode());
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const sizes = useMemo(
    () =>
      ({
        "--map-left-size": preference.leftPanelCollapsed
          ? "0px"
          : preference.leftPanelWidth + "px",
        "--map-left-separator": preference.leftPanelCollapsed ? "0px" : "6px",
        "--map-right-size": preference.rightPanelCollapsed
          ? "0px"
          : preference.rightPanelWidth + "px",
        "--map-right-separator": preference.rightPanelCollapsed ? "0px" : "6px",
        "--map-table-size": preference.attributeTableCollapsed
          ? "0px"
          : preference.attributeTableHeight + "px",
        "--map-table-separator": preference.attributeTableCollapsed ? "0px" : "6px"
      }) as CSSProperties,
    [preference]
  );

  function update(patch: Partial<WorkspaceLayoutPreference>) {
    onPreferenceChange({ ...preference, ...patch });
  }

  return (
    <section
      className={"map-workspace-layout is-" + mode}
      data-testid="map-workspace-layout"
      data-responsive-mode={mode}
      style={sizes}
      aria-label="Bố cục không gian bản đồ"
    >
      <div className="map-layout-controls" aria-label="Điều khiển bố cục">
        <button
          type="button"
          aria-pressed={!preference.leftPanelCollapsed}
          onClick={() =>
            update({ leftPanelCollapsed: !preference.leftPanelCollapsed })
          }
        >
          Lớp dữ liệu
        </button>
        <button
          type="button"
          aria-pressed={!preference.rightPanelCollapsed}
          onClick={() =>
            update({ rightPanelCollapsed: !preference.rightPanelCollapsed })
          }
        >
          Chi tiết
        </button>
        <button
          type="button"
          aria-pressed={!preference.attributeTableCollapsed}
          onClick={() =>
            update({
              attributeTableCollapsed: !preference.attributeTableCollapsed
            })
          }
        >
          Bảng thuộc tính
        </button>
      </div>

      <div
        className={
          preference.leftPanelCollapsed
            ? "map-layout-left is-collapsed"
            : "map-layout-left"
        }
        aria-hidden={preference.leftPanelCollapsed || undefined}
      >
        {left}
      </div>
      {preference.leftPanelCollapsed ? null : (
        <ResizablePanel
          className="map-layout-left-resizer"
          orientation="vertical"
          value={preference.leftPanelWidth}
          min={WORKSPACE_LAYOUT_BOUNDS.leftPanelWidth[0]}
          max={WORKSPACE_LAYOUT_BOUNDS.leftPanelWidth[1]}
          label="Đổi độ rộng bảng lớp dữ liệu"
          onChange={(leftPanelWidth) => update({ leftPanelWidth })}
        />
      )}

      <div className="map-layout-map">{map}</div>

      {preference.rightPanelCollapsed ? null : (
        <ResizablePanel
          className="map-layout-right-resizer"
          orientation="vertical"
          value={preference.rightPanelWidth}
          min={WORKSPACE_LAYOUT_BOUNDS.rightPanelWidth[0]}
          max={WORKSPACE_LAYOUT_BOUNDS.rightPanelWidth[1]}
          label="Đổi độ rộng bảng chi tiết"
          invert
          onChange={(rightPanelWidth) => update({ rightPanelWidth })}
        />
      )}
      <div
        className={
          preference.rightPanelCollapsed
            ? "map-layout-right is-collapsed"
            : "map-layout-right"
        }
        aria-hidden={preference.rightPanelCollapsed || undefined}
      >
        {right}
      </div>

      {preference.attributeTableCollapsed ? null : (
        <ResizablePanel
          className="map-layout-table-resizer"
          orientation="horizontal"
          value={preference.attributeTableHeight}
          min={WORKSPACE_LAYOUT_BOUNDS.attributeTableHeight[0]}
          max={WORKSPACE_LAYOUT_BOUNDS.attributeTableHeight[1]}
          label="Đổi chiều cao bảng thuộc tính"
          invert
          onChange={(attributeTableHeight) => update({ attributeTableHeight })}
        />
      )}
      <div
        className={
          preference.attributeTableCollapsed
            ? "map-layout-table is-collapsed"
            : "map-layout-table"
        }
        aria-hidden={preference.attributeTableCollapsed || undefined}
      >
        {bottom}
      </div>
    </section>
  );
}
