import { formatFeatureValue } from "../spatial/feature-inspector";

// Preserve exact typed values; distinguish absent fields from explicit null.
export function mapFeatureValue(value: string | number | boolean | null | undefined): string {
  return value === undefined ? "Thiếu giá trị" : formatFeatureValue(value);
}

export function geometryStateLabel(value: string): string {
  switch (value) {
    case "available": return "Khả dụng";
    case "present": return "Có hình học";
    case "absent":
    case "empty": return "Không có hình học";
    case "unavailable": return "Không khả dụng";
    case "invalid": return "Không hợp lệ";
    case "unsupported": return "Không hỗ trợ hình học";
    case "omitted": return "Không tải hình học";
    default: return "Trạng thái hình học chưa xác định";
  }
}
