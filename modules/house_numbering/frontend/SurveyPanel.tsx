import {
  getHouseNumberingProgress,
  houseNumberingProgressReportUrl,
  listHouseNumberingBuildings,
  listHouseNumberingSurveys,
  reviewHouseNumberingSurvey,
  syncHouseNumberingSurveys,
  uploadHouseNumberingSurveyPhoto
} from "./api";
import { useEffect, useState } from "react";
import { hnClient, uiError, withCsrf } from "./client";
import { useReloadable } from "./hooks";

type Props = { organizationId: string; projectId: string };

type GpsObservation = {
  x: number;
  y: number;
  crs_code: 4326;
  gps_accuracy_m: number;
};

type QueueItem = {
  client_uuid: string;
  building_id: string;
  condition: string;
  x?: number;
  y?: number;
  crs_code?: number;
  gps_accuracy_m?: number;
  recorded_by_actor_id?: string;
  photo_artifact_ids: string[];
};

export function SurveyPanel({ organizationId, projectId }: Props) {
  const key = `hn-survey-queue:${organizationId}:${projectId}`;
  const buildings = useReloadable(
    () => listHouseNumberingBuildings(hnClient, organizationId, projectId),
    [organizationId, projectId]
  );
  const surveys = useReloadable(
    () => listHouseNumberingSurveys(hnClient, organizationId, projectId),
    [organizationId, projectId]
  );
  const progress = useReloadable(
    () => getHouseNumberingProgress(hnClient, organizationId, projectId),
    [organizationId, projectId]
  );

  const [queue, setQueue] = useState<QueueItem[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(key) ?? "[]") as QueueItem[];
    } catch {
      return [];
    }
  });
  const [buildingId, setBuildingId] = useState("");
  const [condition, setCondition] = useState("house");
  const [photoId, setPhotoId] = useState<string | null>(null);
  const [gps, setGps] = useState<GpsObservation | null>(null);
  const [recordedBy, setRecordedBy] = useState("");
  const [online, setOnline] = useState(navigator.onLine);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(queue));
  }, [key, queue]);

  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  function captureGps() {
    setError(null);
    if (!navigator.geolocation) {
      setError("Thiết bị/trình duyệt không hỗ trợ GPS.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const accuracy = position.coords.accuracy;
        if (!Number.isFinite(accuracy) || accuracy <= 0) {
          setError("Thiết bị không trả về độ chính xác GPS hợp lệ.");
          return;
        }
        setGps({
          x: position.coords.longitude,
          y: position.coords.latitude,
          crs_code: 4326,
          gps_accuracy_m: accuracy
        });
        setNotice(`Đã lấy GPS · độ chính xác thiết bị ±${accuracy.toFixed(1)} m.`);
      },
      (positionError) => {
        setError(`Không lấy được GPS: ${positionError.message}`);
      },
      {
        enableHighAccuracy: true,
        timeout: 15_000,
        maximumAge: 15_000
      }
    );
  }

  async function syncQueue() {
    setError(null);
    try {
      await withCsrf(async () => {
        const result = await syncHouseNumberingSurveys(
          hnClient,
          organizationId,
          projectId,
          queue
        );
        const blocked = new Set(
          result.conflicts.map((item) => String(item.client_uuid ?? ""))
        );
        setQueue((current) =>
          current.filter((item) => blocked.has(item.client_uuid))
        );
        const gpsWarnings = result.warnings
          .map((item) => String(item.code ?? "GPS_WARNING"))
          .join(", ");
        setNotice(
          `Sync: ${result.applied.length} mới, ${result.replayed.length} replay, ` +
            `${result.conflicts.length} xung đột, ${result.warnings.length} cảnh báo` +
            (gpsWarnings ? ` (${gpsWarnings})` : ".")
        );
        await Promise.all([surveys.reload(), progress.reload()]);
      });
    } catch (err) {
      setError(await uiError(err));
    }
  }

  function enqueue() {
    if (!buildingId) return;
    setQueue((current) => [
      ...current,
      {
        client_uuid: crypto.randomUUID(),
        building_id: buildingId,
        condition,
        ...(gps ?? {}),
        ...(recordedBy.trim()
          ? { recorded_by_actor_id: recordedBy.trim() }
          : {}),
        photo_artifact_ids: photoId ? [photoId] : []
      }
    ]);
    setNotice(
      gps
        ? `Đã thêm vào hàng đợi offline với GPS ±${gps.gps_accuracy_m.toFixed(1)} m.`
        : "Đã thêm vào hàng đợi offline; chưa có GPS."
    );
  }

  return (
    <>
      <section className="hn-card">
        <div className={online ? "hn-ok" : "hn-warning"}>
          {online
            ? "Đang online"
            : "Đang offline — phiếu sẽ lưu cục bộ và sync sau."}
        </div>
        <h2>Khảo sát hiện trường offline</h2>
        <div className="hn-form">
          <label>
            Building
            <select
              value={buildingId}
              onChange={(e) => setBuildingId(e.target.value)}
            >
              <option value="">Chọn nhà</option>
              {(buildings.data?.items ?? []).map((building) => (
                <option key={building.id} value={building.id}>
                  {building.parcel_ref ?? building.id.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
          <label>
            Tình trạng
            <select
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
            >
              <option value="house">Có nhà</option>
              <option value="vacant">Đất trống</option>
              <option value="removed">Không còn</option>
              <option value="other">Khác</option>
            </select>
          </label>
          <label>
            Ảnh
            <input
              type="file"
              accept="image/png,image/jpeg"
              disabled={!online}
              onChange={(e) =>
                void (async () => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  try {
                    await withCsrf(async () => {
                      const uploaded = await uploadHouseNumberingSurveyPhoto(
                        hnClient,
                        organizationId,
                        projectId,
                        file
                      );
                      setPhotoId(uploaded.id);
                      setNotice("Đã lưu ảnh có checksum.");
                    });
                  } catch (err) {
                    setError(await uiError(err));
                  }
                })()
              }
            />
          </label>
          <label>
            Gửi hộ cho actor UUID (tùy chọn)
            <input
              value={recordedBy}
              onChange={(e) => setRecordedBy(e.target.value)}
              placeholder="Chỉ người có quyền quản lý được gửi hộ"
            />
          </label>
          <div className="hn-actions">
            <button className="hn-btn secondary" type="button" onClick={captureGps}>
              Lấy GPS
            </button>
            {gps ? (
              <span className="hn-badge">
                EPSG:4326 · ±{gps.gps_accuracy_m.toFixed(1)} m
              </span>
            ) : (
              <span className="hn-muted">Chưa lấy GPS</span>
            )}
          </div>
          <button
            className="hn-btn"
            type="button"
            disabled={!buildingId}
            onClick={enqueue}
          >
            Lưu phiếu
          </button>
          <button
            className="hn-btn"
            type="button"
            disabled={!online || !queue.length}
            onClick={() => void syncQueue()}
          >
            Sync {queue.length} phiếu
          </button>
        </div>
        <p className="hn-muted">
          GPS lưu kèm độ chính xác do thiết bị báo. Nếu sai lệch tới geometry nhà lớn
          hơn độ chính xác đó, API trả cảnh báo và ghi audit; không dùng ngưỡng mét
          hardcode. Client UUID đảm bảo retry không tạo phiếu trùng.
        </p>
      </section>

      <section className="hn-card">
        <h2>Tiến độ</h2>
        <div className="hn-grid">
          <div>
            <div className="hn-kpi">{progress.data?.positions ?? 0}</div>
            vị trí đã chấp nhận
          </div>
          <div>
            <div className="hn-kpi">{progress.data?.completion ?? "—"}%</div>
            hoàn thành theo target
          </div>
          <div>
            <div className="hn-kpi">{progress.data?.submitted_pending ?? 0}</div>
            đang chờ duyệt
          </div>
        </div>
        <a
          className="hn-btn secondary"
          href={houseNumberingProgressReportUrl(organizationId, projectId)}
        >
          Tải báo cáo XLSX
        </a>
      </section>

      <section className="hn-card">
        <h2>Phiếu khảo sát</h2>
        <table className="hn-table">
          <thead>
            <tr>
              <th>Building</th>
              <th>Tình trạng</th>
              <th>GPS</th>
              <th>State</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody>
            {(surveys.data?.items ?? []).map((survey) => (
              <tr key={survey.id}>
                <td>{survey.building_id?.slice(0, 8) ?? "—"}</td>
                <td>{survey.condition}</td>
                <td>
                  {survey.gps_deviation_m == null
                    ? "—"
                    : `${survey.gps_deviation_m.toFixed(1)} m`}
                  {(survey.warnings ?? []).length ? (
                    <div className="hn-warning">
                      {(survey.warnings ?? [])
                        .map((item) => String(item.code ?? "GPS_WARNING"))
                        .join(", ")}
                    </div>
                  ) : null}
                </td>
                <td>{survey.state}</td>
                <td>
                  {survey.state === "submitted" ? (
                    <div className="hn-actions">
                      <button
                        className="hn-btn"
                        onClick={() =>
                          void withCsrf(async () => {
                            await reviewHouseNumberingSurvey(
                              hnClient,
                              organizationId,
                              projectId,
                              survey.id,
                              {
                                expected_revision: survey.revision,
                                decision: "accepted"
                              }
                            );
                            await surveys.reload();
                            await progress.reload();
                          })
                        }
                      >
                        Nhận
                      </button>
                      <button
                        className="hn-btn danger"
                        onClick={() =>
                          void withCsrf(async () => {
                            await reviewHouseNumberingSurvey(
                              hnClient,
                              organizationId,
                              projectId,
                              survey.id,
                              {
                                expected_revision: survey.revision,
                                decision: "rejected"
                              }
                            );
                            await surveys.reload();
                          })
                        }
                      >
                        Từ chối
                      </button>
                    </div>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {notice ? <div className="hn-ok">{notice}</div> : null}
        {error ? <div className="hn-error">{error}</div> : null}
      </section>
    </>
  );
}
