import { describe, expect, it } from "vitest";

import {
  DEFAULT_WORKSPACE_LAYOUT,
  normalizeWorkspaceLayoutPreference,
  saveWorkspaceLayoutPreference
} from "./workspace-layout";

describe("workspace layout preference", () => {
  it("normalizes every canonical field and clamps panel dimensions", () => {
    expect(
      normalizeWorkspaceLayoutPreference({
        leftPanelCollapsed: true,
        rightPanelCollapsed: true,
        attributeTableCollapsed: true,
        leftPanelWidth: 9999,
        rightPanelWidth: 1,
        attributeTableHeight: 9999
      })
    ).toEqual({
      leftPanelCollapsed: true,
      rightPanelCollapsed: true,
      attributeTableCollapsed: true,
      leftPanelWidth: 420,
      rightPanelWidth: 260,
      attributeTableHeight: 420
    });
  });

  it("falls back safely for invalid persisted values", () => {
    expect(
      normalizeWorkspaceLayoutPreference({
        leftPanelWidth: Number.NaN,
        rightPanelWidth: Number.POSITIVE_INFINITY,
        attributeTableHeight: -100
      })
    ).toEqual({
      ...DEFAULT_WORKSPACE_LAYOUT,
      attributeTableHeight: 140
    });
  });

  it("persists only normalized non-sensitive layout data", () => {
    let stored = "";
    saveWorkspaceLayoutPreference(
      {
        ...DEFAULT_WORKSPACE_LAYOUT,
        leftPanelWidth: 900,
        rightPanelCollapsed: true
      },
      {
        setItem: (_key, value) => {
          stored = value;
        }
      }
    );

    expect(JSON.parse(stored)).toEqual({
      ...DEFAULT_WORKSPACE_LAYOUT,
      leftPanelWidth: 420,
      rightPanelCollapsed: true
    });
    expect(stored).not.toContain("organization");
    expect(stored).not.toContain("project");
    expect(stored).not.toContain("feature");
  });
});
