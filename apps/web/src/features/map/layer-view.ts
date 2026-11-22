import type {
  MapLayerReference,
  SpatialLayer
} from "@openvietgis/client-sdk";

export type LayerAvailability =
  | "loading"
  | "usable"
  | "empty"
  | "partial"
  | "stale"
  | "permission"
  | "unsupported"
  | "unavailable"
  | "hidden";

export interface LayerPanelItemView {
  layerId: string;
  name: string;
  visible: boolean;
  active: boolean;
  order: number;
  availability: LayerAvailability;
  availabilityLabel: string;
  canZoom: boolean;
  canMoveUp: boolean;
  canMoveDown: boolean;
  canRemove: boolean;
  disabledReason: string | null;
}

function availabilityFrom(
  layer: SpatialLayer | undefined,
  state: string,
  visible: boolean
): Pick<
  LayerPanelItemView,
  "availability" | "availabilityLabel" | "canZoom" | "disabledReason"
> {
  if (!visible) {
    return {
      availability: "hidden",
      availabilityLabel: "Đang ẩn",
      canZoom: false,
      disabledReason: "Bật hiển thị lớp trước khi thu phóng."
    };
  }
  if (state.startsWith("stale")) {
    return {
      availability: "stale",
      availabilityLabel: "Cần xác thực lại",
      canZoom: false,
      disabledReason: "Dữ liệu lớp đã thay đổi hoặc quyền cần xác thực lại."
    };
  }
  if (!layer) {
    if (state === "permission") {
      return {
        availability: "permission",
        availabilityLabel: "Không đủ quyền",
        canZoom: false,
        disabledReason: "Tài khoản hiện tại không thể đọc thông tin lớp."
      };
    }
    return state.startsWith("unavailable")
      ? {
          availability: "unavailable",
          availabilityLabel: "Không khả dụng",
          canZoom: false,
          disabledReason: "Không thể đọc thông tin lớp hiện tại."
        }
      : {
          availability: "loading",
          availabilityLabel: "Đang kiểm tra",
          canZoom: false,
          disabledReason: "Đang kiểm tra khả năng hiển thị của lớp."
        };
  }

  const render = layer.capabilities.find((item) => item.name === "render");
  if (!render || !render.technical_supported) {
    return {
      availability: "unsupported",
      availabilityLabel: "Không hỗ trợ hiển thị",
      canZoom: false,
      disabledReason: "Kiểu dữ liệu hoặc CRS chưa được hỗ trợ để hiển thị."
    };
  }
  if (!render.actor_authorized) {
    return {
      availability: "permission",
      availabilityLabel: "Không đủ quyền",
      canZoom: false,
      disabledReason: "Tài khoản hiện tại không có quyền hiển thị lớp này."
    };
  }
  if (!render.available || layer.lifecycle !== "active" || layer.source.lifecycle !== "active") {
    return {
      availability: "unavailable",
      availabilityLabel: "Không khả dụng",
      canZoom: false,
      disabledReason: "Nguồn hoặc lớp hiện không ở trạng thái sẵn sàng."
    };
  }
  if (state === "loading") {
    return {
      availability: "loading",
      availabilityLabel: "Đang tải dữ liệu",
      canZoom: true,
      disabledReason: null
    };
  }
  if (state === "empty") {
    return {
      availability: "empty",
      availabilityLabel: "Không có đối tượng trong khung nhìn",
      canZoom: true,
      disabledReason: null
    };
  }
  if (state.startsWith("partial")) {
    return {
      availability: "partial",
      availabilityLabel: "Đang hiển thị một phần",
      canZoom: true,
      disabledReason: null
    };
  }
  if (state.startsWith("unsupported") || state.startsWith("unavailable")) {
    return {
      availability: "unavailable",
      availabilityLabel: "Không khả dụng",
      canZoom: false,
      disabledReason: "Lớp không khả dụng trong khung nhìn hiện tại."
    };
  }

  return {
    availability: "usable",
    availabilityLabel: "Sẵn sàng",
    canZoom: true,
    disabledReason: null
  };
}

export function buildLayerPanelItemView(
  reference: MapLayerReference,
  layer: SpatialLayer | undefined,
  state: string,
  activeLayerId: string | null,
  order: number,
  total: number
): LayerPanelItemView {
  const availability = availabilityFrom(layer, state, reference.visible);
  return {
    layerId: reference.layer_id,
    name: layer?.name ?? (state === "loading" ? "Lớp đang tải" : "Lớp không khả dụng"),
    visible: reference.visible,
    active: activeLayerId === reference.layer_id,
    order,
    ...availability,
    canMoveUp: order > 0,
    canMoveDown: order < total - 1,
    canRemove: true
  };
}
