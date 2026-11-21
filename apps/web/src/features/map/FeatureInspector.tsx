import type {
  SpatialFeatureDetail,
  SpatialLayer
} from "@openvietgis/client-sdk";

import { formatFeatureValue } from "../spatial/feature-inspector";

function geometryStateLabel(value: string): string {
  return {
    available: "Khả dụng",
    present: "Có hình học",
    empty: "Không có hình học",
    unavailable: "Không khả dụng",
    invalid: "Không hợp lệ",
    omitted: "Không tải hình học"
  }[value] ?? value;
}

function crsLabel(code: number | null | undefined): string {
  return code ? "EPSG:" + code : "Chưa xác định";
}

export function FeatureInspector({
  layer,
  detail,
  focus,
  count,
  error
}: {
  layer: SpatialLayer | undefined;
  detail: SpatialFeatureDetail | undefined;
  focus: string | null;
  count: number;
  error: string | null;
}) {
  const activeDetail = focus && !error && detail ? detail : undefined;

  return (
    <aside
      className="map-inspector"
      aria-label="Chi tiết đối tượng bản đồ"
      data-testid="map-inspector"
      data-feature-id={activeDetail?.feature.feature_id}
    >
      <h2>Chi tiết đối tượng</h2>

      {!focus ? (
        <p>
          Bấm chọn một đối tượng trên bản đồ hoặc trong bảng thuộc tính để xem
          chi tiết.
        </p>
      ) : error ? (
        <p role="alert">{error}</p>
      ) : !activeDetail ? (
        <p role="status">Đang tải chi tiết đối tượng…</p>
      ) : (
        <div>
          <h3>Đối tượng {activeDetail.feature.feature_id}</h3>
          <p>
            {count} đang chọn
            {count > 1 ? " · Đang xem đối tượng nổi bật" : ""}
          </p>

          <dl>
            <dt>Lớp dữ liệu</dt>
            <dd>{layer?.name}</dd>
            <dt>CRS gốc</dt>
            <dd>{crsLabel(layer?.source.source_crs?.code)}</dd>
            <dt>CRS lưu trữ</dt>
            <dd>{crsLabel(layer?.source.stored_crs?.code)}</dd>
            <dt>CRS hiển thị</dt>
            <dd>
              {activeDetail.context.response_crs
                ? "EPSG:" +
                  activeDetail.context.response_crs.code +
                  " · thứ tự X/Y"
                : "Chỉ thuộc tính"}
            </dd>
            <dt>Trạng thái hình học</dt>
            <dd>{geometryStateLabel(activeDetail.feature.geometry_state)}</dd>
          </dl>

          <table>
            <thead>
              <tr>
                <th>Trường / Kiểu</th>
                <th>Giá trị</th>
              </tr>
            </thead>
            <tbody>
              {layer?.source.schema.fields.map((field) => (
                <tr key={field.field_id}>
                  <th>
                    {field.name}
                    <small>
                      {field.field_id} · {field.type}
                    </small>
                  </th>
                  <td>
                    <code>
                      {formatFeatureValue(
                        activeDetail.feature.attributes[field.field_id]
                      )}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {activeDetail.context.transformation ? (
            <p className="map-muted">
              Phép chuyển hệ tọa độ hiển thị{" "}
              {activeDetail.context.transformation.operation_id}. Hình học gốc
              không thay đổi.
            </p>
          ) : null}

        </div>
      )}
    </aside>
  );
}
