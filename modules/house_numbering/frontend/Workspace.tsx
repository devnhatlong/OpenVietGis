import {
  createHouseNumberingArea,
  createHouseNumberingBuilding,
  createHouseNumberingRoute,
  deleteHouseNumberingRoute,
  listHouseNumberingAreas,
  listHouseNumberingBuildings,
  listHouseNumberingRoutes,
  setHouseNumberingEligibility,
  type HouseNumberingBuilding
} from "./api";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { DocumentsPanel } from "./DocumentsPanel";
import { NumberingPanel } from "./NumberingPanel";
import { ProposalPanel } from "./ProposalPanel";
import { ReconcilePanel } from "./ReconcilePanel";
import { SearchExportPanel } from "./SearchExportPanel";
import { SurveyPanel } from "./SurveyPanel";
import { hnClient, uiError, withCsrf } from "./client";
import { useReloadable } from "./hooks";

type Props={organizationId:string;projectId:string};
type Tab="registry"|"numbering"|"proposal"|"reconcile"|"survey"|"documents"|"search";

function RegistryPanel({organizationId,projectId}:Props){
 const [params]=useSearchParams();
 const handoffSource=params.get("sourceId")??"";const handoffFeature=params.get("featureId")??"";
 const areas=useReloadable(()=>listHouseNumberingAreas(hnClient,organizationId,projectId),[organizationId,projectId]);
 const routes=useReloadable(()=>listHouseNumberingRoutes(hnClient,organizationId,projectId),[organizationId,projectId]);
 const buildings=useReloadable(()=>listHouseNumberingBuildings(hnClient,organizationId,projectId),[organizationId,projectId]);
 const [areaName,setAreaName]=useState("");const [routeName,setRouteName]=useState("");const [routeSource,setRouteSource]=useState(handoffSource);const [routeFeature,setRouteFeature]=useState(handoffFeature);
 const [buildingSource,setBuildingSource]=useState(handoffSource);const [buildingFeature,setBuildingFeature]=useState(handoffFeature);const [buildingRoute,setBuildingRoute]=useState("");const [parcel,setParcel]=useState("");
 const [notice,setNotice]=useState<string|null>(null);const [error,setError]=useState<string|null>(null);
 async function mutation(action:()=>Promise<void>){setError(null);try{await withCsrf(action);}catch(err){setError(await uiError(err));}}
 async function eligibility(b:HouseNumberingBuilding,value:"eligible"|"ineligible"){await mutation(async()=>{await setHouseNumberingEligibility(hnClient,organizationId,projectId,b.id,{expected_revision:b.revision,eligibility:value,reason:value==="ineligible"?"Đánh dấu từ workspace":null});await buildings.reload();});}
 return <>
  <section className="hn-card"><h2>Cấu trúc địa bàn</h2><div className="hn-form"><label>Tên khu/phường<input value={areaName} onChange={(e)=>setAreaName(e.target.value)}/></label><button className="hn-btn" disabled={!areaName.trim()} onClick={()=>void mutation(async()=>{await createHouseNumberingArea(hnClient,organizationId,projectId,{name:areaName,kind:"current"});setAreaName("");setNotice("Đã thêm khu.");await areas.reload();})}>Thêm khu</button></div><p>{(areas.data?.items??[]).map((a)=><span className="hn-badge" key={a.id}>{a.name}</span>)}</p></section>
  <section className="hn-card"><h2>Tuyến đường / hẻm</h2><div className="hn-form"><label>Tên tuyến<input value={routeName} onChange={(e)=>setRouteName(e.target.value)}/></label><label>Core source UUID<input value={routeSource} onChange={(e)=>setRouteSource(e.target.value)}/></label><label>Feature ID<input value={routeFeature} onChange={(e)=>setRouteFeature(e.target.value)}/></label><button className="hn-btn" disabled={!routeName||!routeSource||!routeFeature} onClick={()=>void mutation(async()=>{await createHouseNumberingRoute(hnClient,organizationId,projectId,{name:routeName,route_type:"street",source_id:routeSource,feature_id:routeFeature,direction_state:"forward",source_label:"core-spatial",status:"confirmed"});setNotice("Đã tạo tuyến liên kết geometry Core.");await routes.reload();})}>Thêm tuyến</button></div><table className="hn-table"><thead><tr><th>Tuyến</th><th>Nguồn geometry</th><th>Số nhà</th><th></th></tr></thead><tbody>{(routes.data?.items??[]).map((r)=><tr key={r.id}><td>{r.name}<br/><small>{r.route_type} · {r.direction_state}</small></td><td><code>{r.linked_source_id?.slice(0,8)} / {r.linked_feature_id}</code></td><td>{r.building_count??0}</td><td><button className="hn-btn danger" disabled={(r.building_count??0)>0} onClick={()=>void mutation(async()=>{await deleteHouseNumberingRoute(hnClient,organizationId,projectId,r.id);await routes.reload();})}>Xóa</button></td></tr>)}</tbody></table></section>
  <section className="hn-card"><h2>Nhà / công trình</h2><div className="hn-form"><label>Tuyến<select value={buildingRoute} onChange={(e)=>setBuildingRoute(e.target.value)}><option value="">Chọn tuyến</option>{(routes.data?.items??[]).map((r)=><option key={r.id} value={r.id}>{r.name}</option>)}</select></label><label>Core source UUID<input value={buildingSource} onChange={(e)=>setBuildingSource(e.target.value)}/></label><label>Feature ID<input value={buildingFeature} onChange={(e)=>setBuildingFeature(e.target.value)}/></label><label>Thửa / parcel<input value={parcel} onChange={(e)=>setParcel(e.target.value)}/></label><button className="hn-btn" disabled={!buildingRoute||!buildingSource||!buildingFeature} onClick={()=>void mutation(async()=>{await createHouseNumberingBuilding(hnClient,organizationId,projectId,{route_id:buildingRoute,source_id:buildingSource,feature_id:buildingFeature,parcel_ref:parcel||null,eligibility:"unknown"});setNotice("Đã thêm công trình.");await Promise.all([buildings.reload(),routes.reload()]);})}>Thêm nhà</button></div><table className="hn-table"><thead><tr><th>Thửa</th><th>Tuyến</th><th>Core feature</th><th>Điều kiện</th><th>Bản đồ</th></tr></thead><tbody>{(buildings.data?.items??[]).map((b)=><tr key={b.id}><td>{b.parcel_ref??"—"}</td><td>{(routes.data?.items??[]).find((r)=>r.id===b.route_id)?.name??"—"}</td><td><code>{b.linked_feature_id}</code></td><td><div className="hn-actions"><span className="hn-badge">{b.eligibility}</span><button className="hn-btn secondary" onClick={()=>void eligibility(b,"eligible")}>Đủ</button><button className="hn-btn secondary" onClick={()=>void eligibility(b,"ineligible")}>Không đủ</button></div></td><td><Link className="hn-btn secondary" to={`/organizations/${organizationId}/projects/${projectId}/map?source=${encodeURIComponent(b.linked_source_id)}&feature=${encodeURIComponent(b.linked_feature_id)}`}>Mở map</Link></td></tr>)}</tbody></table>{notice&&<div className="hn-ok">{notice}</div>}{error&&<div className="hn-error">{error}</div>}</section>
 </>;
}

export function HouseNumberingWorkspace({organizationId,projectId}:Props){
 const [tab,setTab]=useState<Tab>("registry");
 const tabs:Array<[Tab,string]>=[["registry","Địa bàn & Nhà"],["numbering","Đánh số"],["proposal","Phương án"],["reconcile","Đối chiếu"],["survey","Hiện trường"],["documents","Hồ sơ"],["search","Tra cứu & Xuất"]];
 return <div className="hn-shell"><header className="hn-head"><div><strong>OpenVietGIS · Số nhà</strong><div className="hn-muted" style={{color:"#dceaf3"}}>Module official độc lập · geometry dùng Core Spatial</div></div><nav className="hn-actions"><Link to={`/organizations/${organizationId}/projects/${projectId}/map`}>Bản đồ Core</Link><Link to={`/organizations/${organizationId}/projects/${projectId}/platform-hub`}>Nền tảng</Link></nav></header><main className="hn-main"><div className="hn-tabs">{tabs.map(([key,label])=><button key={key} className={`hn-tab ${tab===key?"active":""}`} onClick={()=>setTab(key)}>{label}</button>)}</div>{tab==="registry"&&<RegistryPanel organizationId={organizationId} projectId={projectId}/>} {tab==="numbering"&&<NumberingPanel organizationId={organizationId} projectId={projectId}/>} {tab==="proposal"&&<ProposalPanel organizationId={organizationId} projectId={projectId}/>} {tab==="reconcile"&&<ReconcilePanel organizationId={organizationId} projectId={projectId}/>} {tab==="survey"&&<SurveyPanel organizationId={organizationId} projectId={projectId}/>} {tab==="documents"&&<DocumentsPanel organizationId={organizationId} projectId={projectId}/>} {tab==="search"&&<SearchExportPanel organizationId={organizationId} projectId={projectId}/>}</main></div>;
}
