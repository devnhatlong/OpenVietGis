import {
  createHouseNumberingRule,
  inspectHouseNumberingLocation,
  listHouseNumberingBuildings,
  listHouseNumberingRoutes,
  listHouseNumberingRules,
  previewHouseNumbering,
  applyHouseNumberingPreview,
  type HouseNumberingPreview
} from "./api";
import { useState } from "react";
import { hnClient, uiError, withCsrf } from "./client";
import { useReloadable } from "./hooks";

type Props = { organizationId: string; projectId: string };

export function NumberingPanel({ organizationId, projectId }: Props) {
  const rules = useReloadable(
    () => listHouseNumberingRules(hnClient, organizationId, projectId),
    [organizationId, projectId]
  );
  const routes = useReloadable(
    () => listHouseNumberingRoutes(hnClient, organizationId, projectId),
    [organizationId, projectId]
  );
  const buildings = useReloadable(
    () => listHouseNumberingBuildings(hnClient, organizationId, projectId),
    [organizationId, projectId]
  );
  const [routeId, setRouteId] = useState("");
  const [ruleId, setRuleId] = useState("");
  const [x, setX] = useState("0");
  const [y, setY] = useState("0");
  const [crs, setCrs] = useState("5899");
  const [inspection, setInspection] = useState<Record<string, unknown> | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [preview, setPreview] = useState<HouseNumberingPreview | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ruleVersion, setRuleVersion] = useState("QD-HN-2026");
  const [authority, setAuthority] = useState("");

  async function mutate(action: () => Promise<void>) {
    setError(null); setNotice(null);
    try { await withCsrf(action); } catch (err) { setError(await uiError(err)); }
  }

  return <>
    <section className="hn-card">
      <h2>Quy tắc đánh số</h2>
      <div className="hn-form">
        <label>Phiên bản<input value={ruleVersion} onChange={(e) => setRuleVersion(e.target.value)} /></label>
        <label>Căn cứ pháp lý<input value={authority} onChange={(e) => setAuthority(e.target.value)} placeholder="Số quyết định / văn bản" /></label>
        <button className="hn-btn" type="button" onClick={() => void mutate(async () => {
          await createHouseNumberingRule(hnClient, organizationId, projectId, {
            version: ruleVersion, status: authority.trim() ? "authoritative" : "draft",
            authority_ref: authority.trim() || null, left_odd: true,
            suffix_style: "letters", max_distance_m: 150
          });
          setNotice("Đã tạo phiên bản quy tắc."); await rules.reload();
        })}>Tạo quy tắc</button>
      </div>
      <p className="hn-muted">Chỉ rule có căn cứ authoritative mới cho phép duyệt chính thức.</p>
    </section>

    <section className="hn-card">
      <h2>Kiểm tra vị trí trên tuyến</h2>
      <div className="hn-form">
        <label>Tuyến<select value={routeId} onChange={(e) => setRouteId(e.target.value)}><option value="">Chọn tuyến</option>{(routes.data?.items ?? []).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
        <label>Rule<select value={ruleId} onChange={(e) => setRuleId(e.target.value)}><option value="">Chọn rule</option>{(rules.data?.items ?? []).map((r) => <option key={r.id} value={r.id}>{r.version} · {r.status}</option>)}</select></label>
        <label>X<input value={x} onChange={(e) => setX(e.target.value)} /></label>
        <label>Y<input value={y} onChange={(e) => setY(e.target.value)} /></label>
        <label>EPSG<input value={crs} onChange={(e) => setCrs(e.target.value)} /></label>
        <button className="hn-btn" disabled={!routeId || !ruleId} type="button" onClick={() => void mutate(async () => {
          const result = await inspectHouseNumberingLocation(hnClient, organizationId, projectId, {
            x: Number(x), y: Number(y), crs_code: Number(crs), route_id: routeId, rule_id: ruleId
          });
          setInspection(result as unknown as Record<string, unknown>);
        })}>Kiểm tra</button>
      </div>
      {inspection && <pre className="hn-code">{JSON.stringify(inspection, null, 2)}</pre>}
    </section>

    <section className="hn-card">
      <h2>Preview / Apply hàng loạt</h2>
      <div className="hn-checks">
        {(buildings.data?.items ?? []).map((b) => <label key={b.id}>
          <input type="checkbox" checked={selected.includes(b.id)} onChange={(e) => setSelected((current) => e.target.checked ? [...current, b.id] : current.filter((id) => id !== b.id))} />
          {b.parcel_ref ?? b.id.slice(0, 8)} · {b.eligibility}
        </label>)}
      </div>
      <div className="hn-form">
        <button className="hn-btn" type="button" disabled={!ruleId || selected.length === 0} onClick={() => void mutate(async () => {
          const result = await previewHouseNumbering(hnClient, organizationId, projectId, {
            building_ids: selected, rule_id: ruleId, operation_id: crypto.randomUUID()
          });
          setPreview(result); setNotice(`Preview ${result.candidate_changes.length} thay đổi; chưa ghi dữ liệu.`);
        })}>Preview</button>
        <button className="hn-btn" type="button" disabled={!preview || Boolean(preview.applied_at)} onClick={() => void mutate(async () => {
          if (!preview) return;
          await applyHouseNumberingPreview(hnClient, organizationId, projectId, preview.id);
          setNotice("Đã apply số đề xuất nguyên tử."); setPreview({ ...preview, applied_at: new Date().toISOString() }); await buildings.reload();
        })}>Apply</button>
      </div>
      {preview && <table className="hn-table"><thead><tr><th>Building</th><th>Số cũ</th><th>Số đề xuất</th><th>Bên / lý trình</th><th>Lý do</th></tr></thead><tbody>{preview.candidate_changes.map((c) => <tr key={c.building_id}><td>{c.building_id.slice(0, 8)}</td><td>{c.old_number ?? "—"}</td><td><strong>{c.number}</strong></td><td>{c.side ?? "?"} / {c.measure.toFixed(1)}m</td><td>{c.reason}</td></tr>)}</tbody></table>}
      {preview?.warnings?.length ? <div className="hn-warning">{preview.warnings.join(" · ")}</div> : null}
      {notice && <div className="hn-ok">{notice}</div>}{error && <div className="hn-error">{error}</div>}
    </section>
  </>;
}
