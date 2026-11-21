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

type MobileSheet = "left" | "right" | "table";

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
  const [mobileSheet, setMobileSheet] = useState<MobileSheet | null>(null);
  const mobile = mode === "mobile";
  const leftCollapsed = mobile ? mobileSheet !== "left" : preference.leftPanelCollapsed;
  const rightCollapsed = mobile ? mobileSheet !== "right" : preference.rightPanelCollapsed;
  const tableCollapsed = mobile ? mobileSheet !== "table" : preference.attributeTableCollapsed;

  useEffect(() => {
    const update = () => {
      const nextMode = currentMode();
      setMode(nextMode);
      if (nextMode !== "mobile") setMobileSheet(null);
    };
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

  function toggle(sheet: MobileSheet, patch: Partial<WorkspaceLayoutPreference>) {
    if (mobile) {
      setMobileSheet((previous) => previous === sheet ? null : sheet);
    } else {
      update(patch);
    }
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
          aria-pressed={!leftCollapsed}
          onClick={() =>
            toggle("left", { leftPanelCollapsed: !preference.leftPanelCollapsed })
          }
        >
          Lớp dữ liệu
        </button>
        <button
          type="button"
          aria-pressed={!rightCollapsed}
          onClick={() =>
            toggle("right", { rightPanelCollapsed: !preference.rightPanelCollapsed })
          }
        >
          Chi tiết
        </button>
        <button
          type="button"
          aria-pressed={!tableCollapsed}
          onClick={() =>
            toggle("table", {
              attributeTableCollapsed: !preference.attributeTableCollapsed
            })
          }
        >
          Bảng thuộc tính
        </button>
      </div>

      <div
        className={
          leftCollapsed
            ? "map-layout-left is-collapsed"
            : "map-layout-left"
        }
        aria-hidden={leftCollapsed || undefined}
      >
        {left}
      </div>
      {leftCollapsed ? null : (
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

      {rightCollapsed ? null : (
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
          rightCollapsed
            ? "map-layout-right is-collapsed"
            : "map-layout-right"
        }
        aria-hidden={rightCollapsed || undefined}
      >
        {right}
      </div>

      {tableCollapsed ? null : (
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
          tableCollapsed
            ? "map-layout-table is-collapsed"
            : "map-layout-table"
        }
        aria-hidden={tableCollapsed || undefined}
      >
        {bottom}
      </div>
    </section>
  );
}
