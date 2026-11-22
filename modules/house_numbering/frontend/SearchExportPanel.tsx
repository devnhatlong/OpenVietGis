import {
  createHouseNumberingExport,
  houseNumberingExportDownloadUrl,
  listHouseNumberingBuildings,
  searchHouseNumbers,
  upsertHouseNumberingPrivateHousehold,
  type HouseNumberingExport
} from "./api";
import { useState } from "react";
import { hnClient, uiError, withCsrf } from "./client";
import { useReloadable } from "./hooks";

type Props={organizationId:string;projectId:string};
const publicFields=["building_id","house_number","old_number","proposed_number","approved_number","route_name","area_name","parcel_number","state","crs"];

export function SearchExportPanel({organizationId,projectId}:Props){
 const buildings=useReloadable(()=>listHouseNumberingBuildings(hnClient,organizationId,projectId),[organizationId,projectId]);
 const [query,setQuery]=useState("");const [results,setResults]=useState<Array<Record<string,unknown>>>([]);
 const [fields,setFields]=useState<string[]>(["building_id","house_number","route_name","parcel_number"]);
 const [format,setFormat]=useState<"csv"|"geojson"|"dxf"|"shapefile_zip">("csv");
 const [privateMode,setPrivateMode]=useState(false);const [purpose,setPurpose]=useState("");const [exported,setExported]=useState<HouseNumberingExport|null>(null);
 const [privateBuilding,setPrivateBuilding]=useState("");const [residentName,setResidentName]=useState("");const [contact,setContact]=useState("");const [consent,setConsent]=useState(false);
 const [notice,setNotice]=useState<string|null>(null);const [error,setError]=useState<string|null>(null);
 async function search(){setError(null);try{const r=await searchHouseNumbers(hnClient,organizationId,projectId,query);setResults(r.items);}catch(err){setError(await uiError(err));}}
 return <>
  <section className="hn-card"><h2>Tra cứu</h2><div className="hn-form"><label>Số nhà / số cũ / tuyến / thửa<input value={query} onChange={(e)=>setQuery(e.target.value)} /></label><button className="hn-btn" type="button" disabled={!query.trim()} onClick={()=>void search()}>Tìm</button></div><table className="hn-table"><thead><tr><th>Building</th><th>Tuyến</th><th>Số</th><th>Số cũ</th><th>Thửa</th></tr></thead><tbody>{results.map((r,i)=><tr key={String(r.building_id??i)}><td>{String(r.building_id??"").slice(0,8)}</td><td>{String(r.route_name??"—")}</td><td>{String(r.house_number??"—")}</td><td>{String(r.old_number??"—")}</td><td>{String(r.parcel_number??"—")}</td></tr>)}</tbody></table></section>
  <section className="hn-card"><h2>Dữ liệu hộ dân hạn chế</h2><div className="hn-warning">PII tách khỏi registry công khai. Ghi/đọc/xuất PII cần quyền quản lý, mục đích rõ ràng và được ghi access log.</div><div className="hn-form"><label>Building<select value={privateBuilding} onChange={(e)=>setPrivateBuilding(e.target.value)}><option value="">Chọn nhà</option>{(buildings.data?.items??[]).map((b)=><option key={b.id} value={b.id}>{b.parcel_ref??b.id.slice(0,8)}</option>)}</select></label><label>Tên<input value={residentName} onChange={(e)=>setResidentName(e.target.value)} /></label><label>Liên hệ<input value={contact} onChange={(e)=>setContact(e.target.value)} /></label><label><input type="checkbox" checked={consent} onChange={(e)=>setConsent(e.target.checked)} /> Có căn cứ/đồng ý</label><button className="hn-btn" disabled={!privateBuilding||!purpose.trim()} onClick={()=>void (async()=>{setError(null);try{await withCsrf(async()=>{await upsertHouseNumberingPrivateHousehold(hnClient,organizationId,projectId,{building_id:privateBuilding,purpose,consent,lawful_basis_ref:consent?"user-confirmed":null,protected_data:{name:residentName,contact}});setNotice("Đã lưu dữ liệu hạn chế và access log.");});}catch(err){setError(await uiError(err));}})()}>Lưu PII</button><label>Mục đích<textarea value={purpose} onChange={(e)=>setPurpose(e.target.value)} placeholder="Bắt buộc cho truy cập/xuất PII" /></label></div></section>
  <section className="hn-card"><h2>Xuất và bàn giao</h2><div className="hn-checks">{publicFields.map((field)=><label key={field}><input type="checkbox" checked={fields.includes(field)} onChange={(e)=>setFields((cur)=>e.target.checked?[...cur,field]:cur.filter((x)=>x!==field))}/>{field}</label>)}</div><div className="hn-form"><label>Format<select value={format} onChange={(e)=>setFormat(e.target.value as typeof format)}><option value="csv">CSV</option><option value="geojson">GeoJSON</option><option value="dxf">DXF</option><option value="shapefile_zip">Shapefile ZIP</option></select></label><label><input type="checkbox" checked={privateMode} onChange={(e)=>setPrivateMode(e.target.checked)} /> Gói riêng có PII</label>{privateMode&&<label>Mục đích PII<input value={purpose} onChange={(e)=>setPurpose(e.target.value)} /></label>}<button className="hn-btn" disabled={!fields.length||(privateMode&&!purpose.trim())} onClick={()=>void (async()=>{setError(null);try{await withCsrf(async()=>{const requested=privateMode?["building_id","name","contact"]:fields;const result=await createHouseNumberingExport(hnClient,organizationId,projectId,{fields:requested,output_format:format,include_private:privateMode,purpose:privateMode?purpose:null});setExported(result);setNotice(`Đã tạo gói ${result.record_count} bản ghi, SHA-256 ${result.sha256.slice(0,12)}…`);});}catch(err){setError(await uiError(err));}})()}>Tạo gói xuất</button>{exported&&<a className="hn-btn secondary" href={houseNumberingExportDownloadUrl(organizationId,projectId,exported.artifact_id)}>Tải gói</a>}</div><p className="hn-muted">Mặc định chỉ cho phép field công khai; yêu cầu field PII ở public export bị API từ chối.</p>{notice&&<div className="hn-ok">{notice}</div>}{error&&<div className="hn-error">{error}</div>}</section>
 </>;
}
