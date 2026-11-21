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
type QueueItem = { client_uuid: string; building_id: string; condition: string; x?: number; y?: number; crs_code?: number; photo_artifact_ids: string[] };

export function SurveyPanel({ organizationId, projectId }: Props) {
  const key = `hn-survey-queue:${organizationId}:${projectId}`;
  const buildings = useReloadable(() => listHouseNumberingBuildings(hnClient, organizationId, projectId), [organizationId, projectId]);
  const surveys = useReloadable(() => listHouseNumberingSurveys(hnClient, organizationId, projectId), [organizationId, projectId]);
  const progress = useReloadable(() => getHouseNumberingProgress(hnClient, organizationId, projectId), [organizationId, projectId]);
  const [queue, setQueue] = useState<QueueItem[]>(() => { try { return JSON.parse(localStorage.getItem(key) ?? "[]") as QueueItem[]; } catch { return []; } });
  const [buildingId, setBuildingId] = useState("");
  const [condition, setCondition] = useState("house");
  const [photoId, setPhotoId] = useState<string | null>(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { localStorage.setItem(key, JSON.stringify(queue)); }, [key, queue]);
  useEffect(() => { const f=()=>setOnline(navigator.onLine); window.addEventListener("online",f); window.addEventListener("offline",f); return()=>{window.removeEventListener("online",f);window.removeEventListener("offline",f);}; }, []);

  async function syncQueue() {
    setError(null);
    try {
      await withCsrf(async () => {
        const result = await syncHouseNumberingSurveys(hnClient, organizationId, projectId, queue);
        const blocked = new Set(result.conflicts.map((item) => String(item.client_uuid ?? "")));
        setQueue((current) => current.filter((item) => blocked.has(item.client_uuid)));
        setNotice(`Sync: ${result.applied.length} mới, ${result.replayed.length} replay, ${result.conflicts.length} xung đột.`);
        await Promise.all([surveys.reload(), progress.reload()]);
      });
    } catch (err) { setError(await uiError(err)); }
  }

  return <>
    <section className="hn-card">
      <div className={online ? "hn-ok" : "hn-warning"}>{online ? "Đang online" : "Đang offline — phiếu sẽ lưu cục bộ và sync sau."}</div>
      <h2>Khảo sát hiện trường offline</h2>
      <div className="hn-form">
        <label>Building<select value={buildingId} onChange={(e) => setBuildingId(e.target.value)}><option value="">Chọn nhà</option>{(buildings.data?.items ?? []).map((b) => <option key={b.id} value={b.id}>{b.parcel_ref ?? b.id.slice(0,8)}</option>)}</select></label>
        <label>Tình trạng<select value={condition} onChange={(e) => setCondition(e.target.value)}><option value="house">Có nhà</option><option value="vacant">Đất trống</option><option value="removed">Không còn</option><option value="other">Khác</option></select></label>
        <label>Ảnh<input type="file" accept="image/png,image/jpeg" disabled={!online} onChange={(e) => void (async () => { const file=e.target.files?.[0]; if(!file)return; try { await withCsrf(async()=>{ const uploaded=await uploadHouseNumberingSurveyPhoto(hnClient,organizationId,projectId,file); setPhotoId(uploaded.id); setNotice("Đã lưu ảnh có checksum."); }); } catch(err){setError(await uiError(err));} })()} /></label>
        <button className="hn-btn" type="button" disabled={!buildingId} onClick={() => { setQueue((current) => [...current,{client_uuid:crypto.randomUUID(),building_id:buildingId,condition,photo_artifact_ids:photoId?[photoId]:[]}]); setNotice("Đã thêm vào hàng đợi offline."); }}>Lưu phiếu</button>
        <button className="hn-btn" type="button" disabled={!online || !queue.length} onClick={() => void syncQueue()}>Sync {queue.length} phiếu</button>
      </div>
      <p className="hn-muted">Client UUID đảm bảo retry không tạo phiếu trùng. Xung đột không tự ghi đè.</p>
    </section>
    <section className="hn-card">
      <h2>Tiến độ</h2>
      <div className="hn-grid"><div><div className="hn-kpi">{progress.data?.positions ?? 0}</div>vị trí đã chấp nhận</div><div><div className="hn-kpi">{progress.data?.completion ?? "—"}%</div>hoàn thành theo target</div><div><div className="hn-kpi">{progress.data?.submitted_pending ?? 0}</div>đang chờ duyệt</div></div>
      <a className="hn-btn secondary" href={houseNumberingProgressReportUrl(organizationId,projectId)}>Tải báo cáo XLSX</a>
    </section>
    <section className="hn-card"><h2>Phiếu khảo sát</h2><table className="hn-table"><thead><tr><th>Building</th><th>Tình trạng</th><th>State</th><th>Review</th></tr></thead><tbody>{(surveys.data?.items ?? []).map((s) => <tr key={s.id}><td>{s.building_id?.slice(0,8) ?? "—"}</td><td>{s.condition}</td><td>{s.state}</td><td>{s.state === "submitted" && <div className="hn-actions"><button className="hn-btn" onClick={() => void withCsrf(async()=>{await reviewHouseNumberingSurvey(hnClient,organizationId,projectId,s.id,{expected_revision:s.revision,decision:"accepted"});await surveys.reload();await progress.reload();})}>Nhận</button><button className="hn-btn danger" onClick={() => void withCsrf(async()=>{await reviewHouseNumberingSurvey(hnClient,organizationId,projectId,s.id,{expected_revision:s.revision,decision:"rejected"});await surveys.reload();})}>Từ chối</button></div>}</td></tr>)}</tbody></table>{notice&&<div className="hn-ok">{notice}</div>}{error&&<div className="hn-error">{error}</div>}</section>
  </>;
}
