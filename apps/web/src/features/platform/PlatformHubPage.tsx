import {
  cogoTraverse,
  createExternalConnection,
  createOfflinePackage,
  decideChangeReview,
  getOpsHealthReady,
  getOpsReleaseCapabilities,
  getOrgEntitlement,
  listAllowlistedHosts,
  listCadConversions,
  listChangeReviews,
  listExtensionManifests,
  listExternalConnections,
  listOfflinePackages,
  listProjectActivities,
  listSpatialLayers,
  loadCsrfToken,
  offlinePackageDownloadUrl,
  registerAllowlistedHost
} from "@openvietgis/client-sdk";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { apiClient } from "../../app/api";
import { ProjectToolbar } from "./ProjectToolbar";

type HubTab = "external" | "collab" | "cad" | "field" | "extensions" | "ops";

export function PlatformHubPage() {
  const { organizationId = "", projectId = "" } = useParams();
  const qc = useQueryClient();
  const [tab, setTab] = useState<HubTab>("ops");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // R010 state
  const [extHost, setExtHost] = useState("tiles.example.org");
  const [extUrl, setExtUrl] = useState("https://tiles.example.org/wms");

  // R012 COGO state
  const [originX, setOriginX] = useState("500000");
  const [originY, setOriginY] = useState("2300000");
  const [dist, setDist] = useState("100");
  const [azimuth, setAzimuth] = useState("90");
  const [cogoOut, setCogoOut] = useState<string | null>(null);

  // R013 Field state
  const [pkgName, setPkgName] = useState("Field Offline Bundle");

  const layersQ = useQuery({
    queryKey: ["hub", organizationId, projectId, "layers"],
    queryFn: () => listSpatialLayers(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });
  const allowlistQ = useQuery({
    queryKey: ["hub", organizationId, "allowlist"],
    queryFn: () => listAllowlistedHosts(apiClient, organizationId),
    enabled: Boolean(organizationId)
  });
  const extConnsQ = useQuery({
    queryKey: ["hub", organizationId, projectId, "ext"],
    queryFn: () => listExternalConnections(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });
  const reviewsQ = useQuery({
    queryKey: ["hub", organizationId, projectId, "reviews"],
    queryFn: () => listChangeReviews(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });
  const actsQ = useQuery({
    queryKey: ["hub", organizationId, projectId, "acts"],
    queryFn: () => listProjectActivities(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });
  const cadQ = useQuery({
    queryKey: ["hub", organizationId, projectId, "cad"],
    queryFn: () => listCadConversions(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });
  const fieldQ = useQuery({
    queryKey: ["hub", organizationId, projectId, "field"],
    queryFn: () => listOfflinePackages(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });
  const extManifestsQ = useQuery({
    queryKey: ["hub", organizationId, "manifests"],
    queryFn: () => listExtensionManifests(apiClient, organizationId),
    enabled: Boolean(organizationId)
  });
  const readyQ = useQuery({
    queryKey: ["ops", "ready"],
    queryFn: () => getOpsHealthReady(apiClient)
  });
  const capsQ = useQuery({
    queryKey: ["ops", "caps"],
    queryFn: () => getOpsReleaseCapabilities(apiClient)
  });
  const entQ = useQuery({
    queryKey: ["ops", organizationId, "entitlement"],
    queryFn: () => getOrgEntitlement(apiClient, organizationId),
    enabled: Boolean(organizationId)
  });

  return (
    <div className="ovg-suite" data-testid="platform-hub">
      <ProjectToolbar
        organizationId={organizationId}
        projectId={projectId}
        active="hub"
        title="R010–R015 Trung tâm Nền tảng GIS & Vận hành"
      />
      <main className="ovg-suite-body">
        <div className="ovg-tabs" role="tablist">
          {(
            [
              ["ops", "R015 Vận hành & Sẵn sàng"],
              ["external", "R010 Nguồn dữ liệu ngoài"],
              ["collab", "R011 Cộng tác nhóm"],
              ["cad", "R012 CAD 2D & COGO"],
              ["field", "R013 Hiện trường & Ngoại tuyến"],
              ["extensions", "R014 Nền tảng Module"]
            ] as Array<[HubTab, string]>
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={tab === k}
              className={`ovg-tab ${tab === k ? "active" : ""}`}
              onClick={() => setTab(k)}
            >
              {label}
            </button>
          ))}
        </div>

        {notice && <div className="ovg-notice">{notice}</div>}
        {error && <div className="ovg-error">{error}</div>}

        {tab === "ops" && (
          <section className="ovg-card" data-testid="ops-readiness-panel">
            <h2>R015 Vận hành Production & Năng lực phát hành</h2>
            <p>
              <strong>Trạng thái sẵn sàng:</strong> {readyQ.data?.status ?? "loading"} ·{" "}
              <strong>PostGIS:</strong> {readyQ.data?.postgis_version ?? "—"} ·{" "}
              <strong>Gói cấu hình:</strong> {entQ.data?.plan_tier ?? "self_host_community"} (tách biệt phân quyền R002)
            </p>
            <table className="ovg-table">
              <thead>
                <tr>
                  <th>Phiên bản</th>
                  <th>Năng lực</th>
                  <th>Cột mốc</th>
                  <th>Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {(capsQ.data?.items ?? []).map((c) => (
                  <tr key={c.id}>
                    <td>
                      <strong>{c.id}</strong>
                    </td>
                    <td>{c.name}</td>
                    <td>{c.milestone}</td>
                    <td>
                      <span className="ovg-badge">{c.enabled ? "Đang bật" : "Đã tắt"}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}

        {tab === "external" && (
          <section className="ovg-card">
            <h2>R010 Nguồn dữ liệu ngoài (Allowlist chống SSRF)</h2>
            <div className="ovg-form-row">
              <label>
                Tên miền được phép (Allowlist)
                <input value={extHost} onChange={(e) => setExtHost(e.target.value)} />
              </label>
              <button
                type="button"
                className="ovg-btn"
                onClick={async () => {
                  setError(null);
                  try {
                    const csrf = await loadCsrfToken(apiClient);
                    const al = await registerAllowlistedHost(
                      apiClient,
                      organizationId,
                      { hostname: extHost },
                      csrf
                    );
                    await createExternalConnection(
                      apiClient,
                      organizationId,
                      projectId,
                      {
                        allowlist_id: al.id,
                        name: `WMS ${extHost}`,
                        protocol: "wms",
                        endpoint_url: extUrl
                      },
                      csrf
                    );
                    setNotice(`Allowlisted ${extHost} and registered read-only WMS connection.`);
                    await qc.invalidateQueries({ queryKey: ["hub", organizationId] });
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Failed.");
                  }
                }}
              >
                Thêm Allowlist & Kết nối
              </button>
              <label style={{ flex: 1 }}>
                Endpoint URL
                <input value={extUrl} onChange={(e) => setExtUrl(e.target.value)} />
              </label>
            </div>
            <p>Allowlisted Hosts: {(allowlistQ.data?.items ?? []).map((h) => h.hostname).join(", ") || "None"}</p>
            <ul>
              {(extConnsQ.data?.items ?? []).map((c) => (
                <li key={c.id}>
                  <strong>{c.name}</strong> ({c.protocol}) — {c.endpoint_url}
                  {" — "}{c.lifecycle === "revoked" ? "Đã thu hồi" : "Chưa xác minh · chỉ cấu hình"}
                </li>
              ))}
            </ul>
          </section>
        )}

        {tab === "collab" && (
          <section className="ovg-card">
            <h2>R011 Cộng tác nhóm & Duyệt thay đổi sau Commit</h2>
            <h3>Yêu cầu duyệt thay đổi ({reviewsQ.data?.items.length ?? 0})</h3>
            <ul>
              {(reviewsQ.data?.items ?? []).map((r) => (
                <li key={r.id}>
                  Changeset <code>{r.changeset_id.slice(0, 8)}</code> — <strong>{r.status}</strong>{" "}
                  {r.status === "pending" && (
                    <button
                      type="button"
                      className="ovg-btn ovg-btn-secondary"
                      onClick={async () => {
                        const csrf = await loadCsrfToken(apiClient);
                        await decideChangeReview(
                          apiClient,
                          organizationId,
                          projectId,
                          r.id,
                          { status: "approved", decision_note: "Approved in UI" },
                          csrf
                        );
                        await qc.invalidateQueries({ queryKey: ["hub", organizationId, projectId] });
                      }}
                    >
                      Approve
                    </button>
                  )}
                </li>
              ))}
            </ul>
            <h3>Dòng hoạt động dự án</h3>
            <ul>
              {(actsQ.data?.items ?? []).map((a) => (
                <li key={a.id}>
                  [{a.event_kind}] {a.actor_display}: {a.summary}
                </li>
              ))}
            </ul>
          </section>
        )}

        {tab === "cad" && (
          <section className="ovg-card">
            <h2>R012 Trao đổi CAD 2D DXF & Tính toán COGO chính xác</h2>
            <div className="ovg-form-row">
              <label>
                Tọa độ gốc X
                <input value={originX} onChange={(e) => setOriginX(e.target.value)} />
              </label>
              <label>
                Tọa độ gốc Y
                <input value={originY} onChange={(e) => setOriginY(e.target.value)} />
              </label>
              <label>
                Khoảng cách (m)
                <input value={dist} onChange={(e) => setDist(e.target.value)} />
              </label>
              <label>
                Góc phương vị (độ)
                <input value={azimuth} onChange={(e) => setAzimuth(e.target.value)} />
              </label>
              <button
                type="button"
                className="ovg-btn"
                onClick={async () => {
                  setError(null);
                  try {
                    const csrf = await loadCsrfToken(apiClient);
                    const res = await cogoTraverse(
                      apiClient,
                      organizationId,
                      projectId,
                      {
                        origin: [Number(originX), Number(originY)],
                        distance: Number(dist),
                        azimuth_degrees: Number(azimuth)
                      },
                      csrf
                    );
                    setCogoOut(
                      `Tọa độ điểm tính được: (${res.endpoint[0].toFixed(4)}, ${res.endpoint[1].toFixed(4)})`
                    );
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "COGO computation failed.");
                  }
                }}
              >
                Tính tọa độ điểm cuối
              </button>
            </div>
            {cogoOut && <p className="ovg-notice">{cogoOut}</p>}
            <h3>CAD Conversions ({cadQ.data?.items.length ?? 0})</h3>
            <ul>
              {(cadQ.data?.items ?? []).map((c) => (
                <li key={c.id}>
                  {c.direction.toUpperCase()} {c.filename} ({c.cad_format}, EPSG:{c.crs_code}) —{" "}
                  {c.status}
                </li>
              ))}
            </ul>
          </section>
        )}

        {tab === "field" && (
          <section className="ovg-card">
            <h2>R013 Gói dữ liệu Hiện trường & Ngoại tuyến (GeoPackage)</h2>
            <div className="ovg-form-row">
              <label>
                Tên gói ngoại tuyến
                <input value={pkgName} onChange={(e) => setPkgName(e.target.value)} />
              </label>
              <button
                type="button"
                className="ovg-btn"
                disabled={(layersQ.data?.items.length ?? 0) === 0}
                onClick={async () => {
                  const first = layersQ.data?.items[0];
                  if (!first) return;
                  setError(null);
                  try {
                    const csrf = await loadCsrfToken(apiClient);
                    const pk = await createOfflinePackage(
                      apiClient,
                      organizationId,
                      projectId,
                      {
                        name: pkgName,
                        layer_id: first.id,
                        aoi_bbox: { min_x: 100, min_y: 8, max_x: 112, max_y: 24 },
                        ttl_hours: 48
                      },
                      csrf
                    );
                    setNotice(`Created offline GeoPackage ${pk.name} (${pk.feature_count} features).`);
                    await qc.invalidateQueries({ queryKey: ["hub", organizationId, projectId, "field"] });
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Package build failed.");
                  }
                }}
              >
                Đóng gói GeoPackage ngoại tuyến
              </button>
            </div>
            <ul>
              {(fieldQ.data?.items ?? []).map((p) => (
                <li key={p.id}>
                  <strong>{p.name}</strong> ({p.feature_count} features, expires {p.expires_at}) —{" "}
                  <a
                    href={offlinePackageDownloadUrl(organizationId, projectId, p.id)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download .gpkg
                  </a>
                </li>
              ))}
            </ul>
          </section>
        )}

        {tab === "extensions" && (
          <section className="ovg-card">
            <h2>R014 Nền tảng Module mở rộng động (Manifest)</h2>
            <p>
              Số Manifest Module đã đăng ký trong tổ chức:{" "}
              <strong>{extManifestsQ.data?.items.length ?? 0}</strong>
            </p>
            <ul>
              {(extManifestsQ.data?.items ?? []).map((m) => (
                <li key={m.id}>
                  <strong>{m.display_name}</strong> (<code>{m.extension_key}@{m.version}</code>) —{" "}
                  {m.description}
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </div>
  );
}
