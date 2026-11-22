import { describe, expect, it, vi } from "vitest";

import {
  createCommands,
  createLayerCommands,
  invokeCommand,
  invokeLayerCommand,
  isCanvasCommand
} from "./commands";

describe("map command registry", () => {
  it("shares execution and availability across every UI entry point", () => {
    const run = vi.fn();
    const commands = createCommands(
      {
        hasActive: true,
        hasVisible: true,
        hasSelection: true,
        canSave: true,
        canAddData: true,
        busy: false
      },
      run
    );

    for (const entry of ["toolbar", "context", "search", "shortcut"] as const) {
      expect(invokeCommand(commands, "map.fit-layer", entry)).toBe(true);
    }
    expect(invokeCommand(commands, "map.add-data", "toolbar")).toBe(true);
    expect(run.mock.calls.every((call) => call[0].startsWith("map."))).toBe(true);
  });

  it("separates current permission from technical capability and blocks unknown operations", () => {
    const run = vi.fn();
    const commands = createCommands(
      {
        hasActive: false,
        hasVisible: false,
        hasSelection: false,
        canSave: false,
        canAddData: false,
        busy: false
      },
      run
    );

    expect(invokeCommand(commands, "map.save", "shortcut")).toBe(false);
    expect(invokeCommand(commands, "map.edit", "search")).toBe(false);
    expect(commands.find((item) => item.id === "map.save")?.reason).toContain(
      "project.edit"
    );
    expect(run).not.toHaveBeenCalled();
  });

  it("offers only current named layers and permitted access navigation", () => {
    const run = vi.fn();
    const base = { hasActive: true, hasVisible: true, hasSelection: false,
      canSave: false, busy: false };
    const viewer = createCommands({ ...base, navigation: {
      canManageAccess: false, layers: [{ id: "known", name: "Điểm hiện tại" }]
    } }, run);
    expect(viewer.find(command => command.id === "map.open-layer:known")?.label).toBe("Mở lớp: Điểm hiện tại");
    for (const id of ["map.open-projects", "map.open-catalog", "map.open-transfers", "map.open-layer:known"]) {
      expect(invokeCommand(viewer, id, "search")).toBe(true);
    }
    expect(invokeCommand(viewer, "map.open-layer:foreign", "search")).toBe(false);
    expect(invokeCommand(viewer, "map.open-access", "search")).toBe(false);
    expect(viewer.filter(isCanvasCommand).map(command => command.id)).not.toContain("map.open-layer:known");
    const manager = createCommands({ ...base, navigation: { canManageAccess: true, layers: [] } }, run);
    expect(invokeCommand(manager, "map.open-access", "search")).toBe(true);
    const busy = createCommands({ ...base, busy: true, navigation: { canManageAccess: true, layers: [] } }, run);
    expect(invokeCommand(busy, "map.open-access", "search")).toBe(false);
    expect(run).toHaveBeenCalledTimes(5);
  });

  it("uses one command model for layer zoom, reorder, visibility and remove", () => {
    const run = vi.fn();
    const commands = createLayerCommands(
      {
        name: "Điểm",
        canZoom: true,
        canMoveUp: false,
        canMoveDown: true,
        visible: true,
        canRemove: true,
        locked: false,
        disabledReason: null
      },
      run
    );

    expect(invokeLayerCommand(commands, "layer.zoom")).toBe(true);
    expect(invokeLayerCommand(commands, "layer.move-up")).toBe(false);
    expect(invokeLayerCommand(commands, "layer.move-down")).toBe(true);
    expect(invokeLayerCommand(commands, "layer.toggle-visibility")).toBe(true);
    expect(invokeLayerCommand(commands, "layer.remove")).toBe(true);
    expect(run).toHaveBeenCalledTimes(4);
  });
});
