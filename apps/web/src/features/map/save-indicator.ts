import type { SaveStatus } from "./save";

export type SaveIndicatorState =
  | "clean"
  | "dirty"
  | "saving"
  | "saved"
  | "conflict"
  | "failed"
  | "unresolved";

export interface SaveIndicatorView {
  state: SaveIndicatorState;
  label: string;
  detail: string;
}

export function deriveSaveIndicatorState({
  dirty,
  pendingStatus
}: {
  dirty: boolean;
  pendingStatus: SaveStatus | null;
}): SaveIndicatorState {
  if (pendingStatus === "saving") return "saving";
  if (pendingStatus === "committed") return "saved";
  if (pendingStatus === "conflict") return "conflict";
  if (pendingStatus === "unresolved") return "unresolved";
  if (pendingStatus === "denied" || pendingStatus === "failed") return "failed";
  return dirty ? "dirty" : "clean";
}

export function buildSaveIndicatorView({
  dirty,
  pendingStatus,
  revision
}: {
  dirty: boolean;
  pendingStatus: SaveStatus | null;
  revision: number;
}): SaveIndicatorView {
  const state = deriveSaveIndicatorState({ dirty, pendingStatus });

  switch (state) {
    case "clean":
      return {
        state,
        label: "Đã lưu",
        detail: "Phiên bản bản đồ " + revision
      };
    case "dirty":
      return {
        state,
        label: "Có thay đổi chưa lưu",
        detail: "Phiên bản dùng chung hiện tại " + revision
      };
    case "saving":
      return {
        state,
        label: "Đang lưu…",
        detail: "Đang chờ hệ thống xác nhận bản lưu"
      };
    case "saved":
      return {
        state,
        label: "Đã lưu phiên bản bản đồ " + revision,
        detail: "Bản lưu đã được hệ thống xác nhận"
      };
    case "conflict":
      return {
        state,
        label: "Có phiên bản mới",
        detail: "Tải lại hoặc đối chiếu trước khi lưu tiếp"
      };
    case "failed":
      return {
        state,
        label: "Lưu thất bại",
        detail: "Phiên bản trước vẫn được giữ nguyên"
      };
    case "unresolved":
      return {
        state,
        label: "Chưa xác định kết quả lưu",
        detail: "Cần đối chiếu thao tác đang chờ trước khi lưu mới"
      };
  }
}
