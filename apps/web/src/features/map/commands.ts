export type MapCommandId =
  | "map.add-data"
  | "map.fit-layer"
  | "map.fit-all"
  | "map.fit-selection"
  | "map.clear-selection"
  | "map.save"
  | "map.set-default-viewpoint"
  | "map.zoom-in"
  | "map.zoom-out";

export type LayerCommandId =
  | "layer.zoom"
  | "layer.move-up"
  | "layer.move-down"
  | "layer.toggle-visibility"
  | "layer.remove";

export type EntryPoint = "toolbar" | "context" | "search" | "shortcut";

export interface MapCommand {
  id: MapCommandId;
  label: string;
  enabled: boolean;
  reason: string | null;
  execute: () => void;
}

export interface LayerCommand {
  id: LayerCommandId;
  label: string;
  enabled: boolean;
  reason: string | null;
  execute: () => void;
}

export interface CommandContext {
  hasActive: boolean;
  hasVisible: boolean;
  hasSelection: boolean;
  canSave: boolean;
  busy: boolean;
  canAddData?: boolean;
}

export interface LayerCommandContext {
  name: string;
  canZoom: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  visible: boolean;
  canRemove: boolean;
  locked: boolean;
  disabledReason: string | null;
}

export function createCommands(
  context: CommandContext,
  run: (id: MapCommandId) => void
): MapCommand[] {
  const definitions: [MapCommandId, string, boolean, string][] = [
    [
      "map.add-data",
      "Thêm dữ liệu",
      context.canAddData ?? false,
      "Tạm thời không thể thêm dữ liệu."
    ],
    [
      "map.fit-layer",
      "Thu phóng lớp đang chọn",
      context.hasActive,
      "Chọn một lớp hỗ trợ hiển thị."
    ],
    [
      "map.fit-all",
      "Thu phóng toàn bộ lớp hiển thị",
      context.hasVisible,
      "Thêm ít nhất một lớp đang bật hiển thị."
    ],
    [
      "map.fit-selection",
      "Thu phóng vùng chọn",
      context.hasSelection,
      "Chọn đối tượng có hình học hợp lệ."
    ],
    [
      "map.clear-selection",
      "Bỏ chọn",
      context.hasSelection,
      "Chưa có đối tượng nào được chọn."
    ],
    [
      "map.save",
      "Lưu bản đồ",
      context.canSave,
      "Cần quyền chỉnh sửa dự án (project.edit)."
    ],
    [
      "map.set-default-viewpoint",
      "Đặt góc nhìn mặc định",
      context.canSave,
      "Cần quyền chỉnh sửa dự án (project.edit)."
    ],
    ["map.zoom-in", "Phóng to (+)", true, ""],
    ["map.zoom-out", "Thu nhỏ (-)", true, ""]
  ];

  return definitions.map(([id, label, enabled, reason]) => ({
    id,
    label,
    enabled: enabled && !context.busy,
    reason: context.busy
      ? "Đang xử lý tác vụ..."
      : enabled
        ? null
        : reason,
    execute: () => run(id)
  }));
}

export function createLayerCommands(
  context: LayerCommandContext,
  run: (id: LayerCommandId) => void
): LayerCommand[] {
  const blocked = context.locked;
  const reason = blocked ? "Bản đồ đang xử lý tác vụ." : null;
  const definitions: [LayerCommandId, string, boolean, string | null][] = [
    [
      "layer.zoom",
      "Thu phóng tới lớp",
      context.canZoom,
      context.disabledReason
    ],
    [
      "layer.move-up",
      "Đưa lên trên",
      context.canMoveUp,
      "Lớp đã ở vị trí trên cùng."
    ],
    [
      "layer.move-down",
      "Đưa xuống dưới",
      context.canMoveDown,
      "Lớp đã ở vị trí dưới cùng."
    ],
    [
      "layer.toggle-visibility",
      context.visible ? "Ẩn lớp" : "Hiện lớp",
      true,
      null
    ],
    ["layer.remove", "Gỡ khỏi bản đồ", context.canRemove, null]
  ];

  return definitions.map(([id, label, enabled, disabledReason]) => ({
    id,
    label,
    enabled: enabled && !blocked,
    reason: reason ?? (enabled ? null : disabledReason),
    execute: () => run(id)
  }));
}

export function invokeCommand(
  commands: MapCommand[],
  id: string,
  _entry: EntryPoint
): boolean {
  void _entry;
  const command = commands.find((item) => item.id === id);
  if (!command?.enabled) return false;
  command.execute();
  return true;
}

export function invokeLayerCommand(
  commands: LayerCommand[],
  id: LayerCommandId
): boolean {
  const command = commands.find((item) => item.id === id);
  if (!command?.enabled) return false;
  command.execute();
  return true;
}
