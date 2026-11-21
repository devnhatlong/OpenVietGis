export interface WorkspaceLayoutPreference {
  leftPanelCollapsed: boolean;
  rightPanelCollapsed: boolean;
  attributeTableCollapsed: boolean;
  leftPanelWidth: number;
  rightPanelWidth: number;
  attributeTableHeight: number;
}

export const DEFAULT_WORKSPACE_LAYOUT: WorkspaceLayoutPreference = {
  leftPanelCollapsed: false,
  rightPanelCollapsed: false,
  attributeTableCollapsed: false,
  leftPanelWidth: 260,
  rightPanelWidth: 300,
  attributeTableHeight: 220
};

export const WORKSPACE_LAYOUT_BOUNDS = {
  leftPanelWidth: [220, 420] as const,
  rightPanelWidth: [260, 440] as const,
  attributeTableHeight: [140, 420] as const
};

const STORAGE_KEY = "openvietgis:map-workspace-layout:v1";

function bounded(value: unknown, [min, max]: readonly [number, number], fallback: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return fallback;
  return Math.max(min, Math.min(max, Math.round(value)));
}

export function normalizeWorkspaceLayoutPreference(
  value: Partial<WorkspaceLayoutPreference> | null | undefined
): WorkspaceLayoutPreference {
  return {
    leftPanelCollapsed:
      typeof value?.leftPanelCollapsed === "boolean"
        ? value.leftPanelCollapsed
        : DEFAULT_WORKSPACE_LAYOUT.leftPanelCollapsed,
    rightPanelCollapsed:
      typeof value?.rightPanelCollapsed === "boolean"
        ? value.rightPanelCollapsed
        : DEFAULT_WORKSPACE_LAYOUT.rightPanelCollapsed,
    attributeTableCollapsed:
      typeof value?.attributeTableCollapsed === "boolean"
        ? value.attributeTableCollapsed
        : DEFAULT_WORKSPACE_LAYOUT.attributeTableCollapsed,
    leftPanelWidth: bounded(
      value?.leftPanelWidth,
      WORKSPACE_LAYOUT_BOUNDS.leftPanelWidth,
      DEFAULT_WORKSPACE_LAYOUT.leftPanelWidth
    ),
    rightPanelWidth: bounded(
      value?.rightPanelWidth,
      WORKSPACE_LAYOUT_BOUNDS.rightPanelWidth,
      DEFAULT_WORKSPACE_LAYOUT.rightPanelWidth
    ),
    attributeTableHeight: bounded(
      value?.attributeTableHeight,
      WORKSPACE_LAYOUT_BOUNDS.attributeTableHeight,
      DEFAULT_WORKSPACE_LAYOUT.attributeTableHeight
    )
  };
}

export function loadWorkspaceLayoutPreference(storage: Pick<Storage, "getItem"> = localStorage): WorkspaceLayoutPreference {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_WORKSPACE_LAYOUT };
    return normalizeWorkspaceLayoutPreference(
      JSON.parse(raw) as Partial<WorkspaceLayoutPreference>
    );
  } catch {
    return { ...DEFAULT_WORKSPACE_LAYOUT };
  }
}

export function saveWorkspaceLayoutPreference(
  value: WorkspaceLayoutPreference,
  storage: Pick<Storage, "setItem"> = localStorage
): void {
  try {
    storage.setItem(
      STORAGE_KEY,
      JSON.stringify(normalizeWorkspaceLayoutPreference(value))
    );
  } catch {
    // Personal layout persistence is optional and must never block Map access.
  }
}
