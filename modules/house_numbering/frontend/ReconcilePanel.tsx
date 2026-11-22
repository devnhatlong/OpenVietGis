import {
  importHouseNumberingEvidence,
  listHouseNumberingReconciliation,
  rebuildHouseNumberingReconciliation,
  resolveHouseNumberingCase,
  type HouseNumberingReconcileCase
} from "./api";
import { useState } from "react";
import { hnClient, uiError, withCsrf } from "./client";
import { useReloadable } from "./hooks";

type Props = { organizationId: string; projectId: string };

export function ReconcilePanel({ organizationId, projectId }: Props) {
  const cases = useReloadable(() => listHouseNumberingReconciliation(hnClient, organizationId, projectId), [organizationId, projectId]);
  const [file, setFile] = useState<File | null>(null);
  const [origin, setOrigin] = useState("certificate");
  const [mappingText, setMappingText] = useState('{"building_id":"building_id","route_id":"route_id","raw_number":"raw_number","source_reference":"source_reference"}');
  const [sourceRef, setSourceRef] = useState("Nguồn nhập liệu");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function mutation(action: () => Promise<void>) {
    setError(null); setNotice(null);
    try { await withCsrf(action); } catch (err) { setError(await uiError(err)); }
  }
  async function resolve(item: HouseNumberingReconcileCase, status: "resolved" | "ignored") {
    await mutation(async () => {
      await resolveHouseNumberingCase(hnClient, organizationId, projectId, item.id, {
        expected_revision: item.revision, status, resolution: status === "resolved" ? "Đã đối chiếu thủ công" : "Bỏ qua có chủ đích"
      });
      await cases.reload();
    });
  }

  return <>
    <section className="hn-card">
      <h2>Nhập nguồn chứng cứ</h2>
      <div className="hn-form">
        <label>File<input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
        <label>Nguồn<select value={origin} onChange={(e) => setOrigin(e.target.value)}><option value="certificate">Giấy chứng nhận</option><option value="cad">CAD</option><option value="survey">Khảo sát</option><option value="legacy">Dữ liệu cũ</option></select></label>
        <label>Tham chiếu nguồn<input value={sourceRef} onChange={(e) => setSourceRef(e.target.value)} /></label>
        <label>Mapping JSON<textarea value={mappingText} onChange={(e) => setMappingText(e.target.value)} /></label>
        <button className="hn-btn" type="button" disabled={!file} onClick={() => void mutation(async () => {
          if (!file) return;
          const ext = file.name.toLowerCase().split(".").pop();
          const format = ext === "xlsx" ? "xlsx" : ext === "geojson" || ext === "json" ? "geojson" : ext === "dxf" ? "dxf" : ext === "zip" ? "shapefile_zip" : "csv";
          const mapping = JSON.parse(mappingText) as Record<string, string>;
          const result = await importHouseNumberingEvidence(hnClient, organizationId, projectId, { file, source_format: format, origin, mapping, default_source_reference: sourceRef });
          const batch = result.batch as { read_count?: number; accepted_count?: number; rejected_count?: number };
          setNotice(`Đã đọc ${batch.read_count ?? 0}, nhận ${batch.accepted_count ?? 0}, loại ${batch.rejected_count ?? 0}${result.replayed ? " · replay không nhân đôi" : ""}.`);
        })}>Nhập & chuẩn hóa</button>
      </div>
    </section>
    <section className="hn-card">
      <div className="hn-actions"><h2 style={{marginRight:"auto"}}>Hàng đợi đối chiếu</h2><button className="hn-btn" type="button" onClick={() => void mutation(async () => { await rebuildHouseNumberingReconciliation(hnClient, organizationId, projectId, {}); await cases.reload(); setNotice("Đã rebuild hàng đợi."); })}>Rebuild</button></div>
      <table className="hn-table"><thead><tr><th>Nhóm</th><th>Building</th><th>Estimated</th><th>Trạng thái</th><th>Xử lý</th></tr></thead><tbody>{(cases.data?.items ?? []).map((item) => <tr key={item.id}><td>{item.case_class}</td><td>{item.building_id?.slice(0,8) ?? "Chưa ghép"}</td><td>{item.estimated ? "Có" : "Không"}</td><td>{item.status}</td><td>{item.status === "open" && <div className="hn-actions"><button className="hn-btn" type="button" onClick={() => void resolve(item,"resolved")}>Đã xử lý</button><button className="hn-btn secondary" type="button" onClick={() => void resolve(item,"ignored")}>Bỏ qua</button></div>}</td></tr>)}</tbody></table>
      {notice && <div className="hn-ok">{notice}</div>}{error && <div className="hn-error">{error}</div>}
    </section>
  </>;
}
