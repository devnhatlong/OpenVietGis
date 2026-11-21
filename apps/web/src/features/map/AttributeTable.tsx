import type {
  SpatialFeaturePage,
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

export function AttributeTable({
  layer,
  page,
  selected,
  focus,
  select,
  previous,
  next,
  pageNumber,
  error
}: {
  layer: SpatialLayer | undefined;
  page: SpatialFeaturePage | undefined;
  selected: string[];
  focus: string | null;
  select: (id: string, multiple: boolean) => void;
  previous: (() => void) | null;
  next: (() => void) | null;
  pageNumber: number;
  error: string | null;
}) {
  const fields = layer?.source.schema.fields ?? [];

  return (
    <section className="map-attributes" aria-label="Bảng thuộc tính bản đồ">
      <header>
        <h2>
          Bảng thuộc tính {layer ? <span>· {layer.name}</span> : null}
        </h2>
        <p>
          {selected.length} đang chọn · trang {pageNumber}
          {selected.length >= 100 ? " · Giới hạn chọn 100" : ""}
        </p>
      </header>

      {!layer ? (
        <p>Chọn một lớp dữ liệu để xem bảng thuộc tính.</p>
      ) : error ? (
        <p role="alert">{error}</p>
      ) : !page ? (
        <p role="status">Đang tải danh sách đối tượng…</p>
      ) : (
        <>
          <div className="map-table-scroll">
            <table aria-label="Bảng thuộc tính theo phiên bản">
              <thead>
                <tr>
                  <th>Chọn</th>
                  <th>Mã đối tượng</th>
                  {fields.map((field) => (
                    <th key={field.field_id}>
                      {field.name}
                      <small>
                        {field.field_id} · {field.type}
                      </small>
                    </th>
                  ))}
                  <th>Trạng thái hình học</th>
                </tr>
              </thead>
              <tbody>
                {page.items.map((feature) => (
                  <tr
                    key={feature.feature_id}
                    className={
                      focus === feature.feature_id
                        ? "is-focused"
                        : selected.includes(feature.feature_id)
                          ? "is-selected"
                          : ""
                    }
                  >
                    <td>
                      <input
                        type="checkbox"
                        aria-label={"Chọn " + feature.feature_id}
                        data-testid={"feature-select-" + feature.feature_id}
                        checked={selected.includes(feature.feature_id)}
                        onChange={() => select(feature.feature_id, true)}
                      />
                    </td>
                    <th>
                      <button
                        type="button"
                        onClick={() => select(feature.feature_id, false)}
                      >
                        {feature.feature_id}
                      </button>
                    </th>
                    {fields.map((field) => (
                      <td key={field.field_id}>
                        <code>
                          {formatFeatureValue(
                            feature.attributes[field.field_id]
                          )}
                        </code>
                      </td>
                    ))}
                    <td>{geometryStateLabel(feature.geometry_state)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!page.items.length ? (
              <p>Không có bản ghi nào ở trang này.</p>
            ) : null}
          </div>

          <footer>
            <button disabled={!previous} onClick={() => previous?.()}>
              Trang trước
            </button>
            <button disabled={!next} onClick={() => next?.()}>
              Trang sau
            </button>
            <span>
              Vùng chọn giữ ổn định mã đối tượng khi chuyển trang.
            </span>
          </footer>
        </>
      )}
    </section>
  );
}
