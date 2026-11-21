import {
  ApiError,
  type ExternalConnection,
  type ExternalProviderPreview,
  loadCsrfToken,
  previewExternalProvider
} from "@openvietgis/client-sdk";
import { useState } from "react";
import { apiClient } from "../../app/api";
import { externalAvailabilityLabel } from "./platform-release-state";

interface Props {
  connection: ExternalConnection;
  organizationId: string;
  projectId: string;
}

/** This is a fresh sample, not a promise of permanent availability. */
export function ExternalSourcePreview({ connection, organizationId, projectId }: Props) {
  const [preview, setPreview] = useState<ExternalProviderPreview | null>(null);
  const [pending, setPending] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const supported = ["wms", "wfs_ogc_features", "wmts_xyz", "cog_geotiff"].includes(connection.protocol);

  if (connection.lifecycle === "revoked" || connection.availability === "revoked") {
    return <span> — {externalAvailabilityLabel(connection)}</span>;
  }
  if (!supported) return <span> — Chưa hỗ trợ xem mẫu · chỉ cấu hình</span>;

  const verify = async () => {
    setPending(true);
    setPreview(null);
    setFailure(null);
    try {
      const csrf = await loadCsrfToken(apiClient);
      const response = await previewExternalProvider(
        apiClient, organizationId, projectId, connection.id, csrf
      );
      if (
        response.connection_id !== connection.id ||
        response.cache_generation !== connection.cache_generation ||
        response.availability !== "available"
      ) {
        setFailure("Nguồn thay đổi trong khi xác minh. Vui lòng thử lại.");
      } else {
        setPreview(response);
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 502) {
        setFailure("Nguồn hiện không khả dụng: không thể xác minh dữ liệu trả về.");
      } else if (error instanceof ApiError && error.status === 403) {
        setFailure("Nguồn bị vô hiệu, chưa được quản trị viên phê duyệt hoặc thiếu quyền.");
      } else {
        setFailure("Không thể xác minh nguồn. Vui lòng thử lại.");
      }
    } finally {
      setPending(false);
    }
  };

  return (
    <div>
      <span>{externalAvailabilityLabel(connection)}</span>{" "}
      <button type="button" className="ovg-btn ovg-btn-secondary" disabled={pending} onClick={verify}>
        {pending ? "Đang xác minh..." : "Xác minh & xem mẫu được phép"}
      </button>
      {failure && <p role="alert">{failure}</p>}
      {preview && (
        <section aria-label="Mẫu dữ liệu đã xác minh">
          <p><strong>Đã xác minh mẫu tại thời điểm yêu cầu</strong> — EPSG:{preview.crs}</p>
          <p>Vùng mẫu do quản trị viên duyệt: {preview.bbox.join(", ")}</p>
          {preview.image_png_base64 && preview.capabilities.render && (
            <img
              alt={`Ảnh raster ${preview.layer_identifier} tại vùng mẫu đã duyệt`}
              width={preview.width}
              height={preview.height}
              src={`data:image/png;base64,${preview.image_png_base64}`}
              style={{ maxWidth: "100%", height: "auto" }}
            />
          )}
          {preview.sample?.kind === "geotiff_range_sample" && (
            <p>
              Mẫu GeoTIFF range: {preview.sample.tile_count} tile, {preview.sample.band_count} kênh,
              kích thước pixel {preview.sample.pixel_size.join(" × ")};
              chưa hỗ trợ đọc cửa sổ COG lớn.
            </p>
          )}
          {(preview.sample?.kind === "xyz" || preview.sample?.kind === "wmts") && (
            <p>Tile {preview.sample.kind.toUpperCase()}: z={preview.sample.z}, x={preview.sample.x}, y={preview.sample.y}</p>
          )}
          {preview.feature_collection && preview.capabilities.feature_read && (
            <>
              <p>Đối tượng trong mẫu: {preview.feature_collection.features.length}</p>
              <details>
                <summary>Xem dữ liệu GeoJSON đã xác minh</summary>
                <pre style={{ maxHeight: 300, overflow: "auto" }}>
                  {JSON.stringify(preview.feature_collection, null, 2)}
                </pre>
              </details>
            </>
          )}
          <p>Ghi công: {preview.attribution} · Quyền sử dụng: {preview.license_text}</p>
          <p>Mẫu chỉ đọc, không bật chỉnh sửa, phân tích, tải xuất hay ngoại tuyến.</p>
          <button type="button" className="ovg-btn ovg-btn-secondary" onClick={() => setPreview(null)}>
            Đóng mẫu
          </button>
        </section>
      )}
    </div>
  );
}
