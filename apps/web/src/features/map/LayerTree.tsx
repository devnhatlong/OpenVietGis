import { useState } from "react";
import type { MapLayerReference,SpatialLayer } from "@openvietgis/client-sdk";
import { capability,defaultStyle,previewMove } from "./workspace";
export function LayerTree({layers,metadata,active,catalog,nextCatalog,previousCatalog,change,choose,locked,states}:{layers:MapLayerReference[];metadata:(SpatialLayer|undefined)[];active:string|null;catalog:SpatialLayer[]|undefined;nextCatalog:(()=>void)|null;previousCatalog:(()=>void)|null;change:(layers:MapLayerReference[])=>void;choose:(id:string)=>void;locked:boolean;states:string[]}) {
 const [add,setAdd]=useState("");
 return <aside className="map-layers" aria-label="Map layer tree">
  <h2>Layers <span className="map-badge">{layers.length}/32</span></h2>
  <label>Add a catalog Layer <select data-testid="add-map-layer" aria-label="Add a catalog Layer" value={add} onChange={e=>setAdd(e.target.value)} disabled={locked||!catalog}><option value="">Choose Layer…</option>{catalog?.filter(l=>!layers.some(r=>r.layer_id===l.id)).map(l=><option key={l.id} value={l.id}>{l.name}{capability(l,"render")?"":" (render unavailable)"}</option>)}</select></label>
  <button type="button" disabled={locked||!add||layers.length>=32} onClick={()=>{if(add){change([...layers,{layer_id:add,visible:true,style:{...defaultStyle}}]);choose(add);setAdd("");}}}>Add Layer</button>
  <div className="map-catalog-pages"><button disabled={!previousCatalog} onClick={()=>previousCatalog?.()}>Previous catalog Layers</button><button disabled={!nextCatalog} onClick={()=>nextCatalog?.()}>Next catalog Layers</button></div>
  {!catalog?<p role="status">Checking catalog access…</p>:null}
  {!layers.length?<p className="map-empty">Add a registered Layer to view your data. Create reference Layers in the spatial catalog.</p>:null}
  <ol>{layers.map((ref,index)=>{const layer=metadata[index],name=layer?.name??"Unavailable reference";return <li key={ref.layer_id} data-testid={"map-layer-"+ref.layer_id} className={active===ref.layer_id?"is-active":""}>
   <div className="map-layer-title"><input type="checkbox" aria-label={"Show "+name} checked={ref.visible} disabled={locked} onChange={()=>change(layers.map(l=>l.layer_id===ref.layer_id?{...l,visible:!l.visible}:l))}/><button type="button" aria-label={"Make "+name+" active"} aria-pressed={active===ref.layer_id} onClick={()=>choose(ref.layer_id)}>{name}</button></div>
   <p data-testid={"viewport-state-"+ref.layer_id}>{states[index]??"loading"}</p>
   {layer?<p className="map-muted">{layer.source.schema.geometry_family} · Native EPSG:{layer.source.stored_crs?.code??"unknown"}<br/><code>{layer.id}</code></p>:null}
   <div className="map-layer-tools"><button type="button" disabled={locked||index===0} aria-label={"Move "+name+" up"} onClick={()=>change(previewMove(layers,ref.layer_id,-1))}>↑</button><button type="button" disabled={locked||index===layers.length-1} aria-label={"Move "+name+" down"} onClick={()=>change(previewMove(layers,ref.layer_id,1))}>↓</button><button type="button" disabled={locked} aria-label={"Remove "+name+" from map"} onClick={()=>change(layers.filter(l=>l.layer_id!==ref.layer_id))}>Remove</button></div>
   <details><summary>Basic appearance</summary><fieldset disabled={locked||!capability(layer,"style")}><label>Color <input type="color" aria-label={"Color "+name} data-testid={"color-"+ref.layer_id} value={ref.style.color} onChange={e=>change(layers.map(l=>l.layer_id===ref.layer_id?{...l,style:{...l.style,color:e.target.value}}:l))}/></label>{(["opacity","width","radius"] as const).map(key=><label key={key}>{key}<input type="range" aria-label={key+" "+name} min={key==="opacity"?0:key==="width"?1:2} max={key==="opacity"?1:key==="width"?12:20} step={key==="opacity"?.1:1} value={ref.style[key]} onChange={e=>change(layers.map(l=>l.layer_id===ref.layer_id?{...l,style:{...l.style,[key]:Number(e.target.value)}}:l))}/><output>{ref.style[key]}</output></label>)}</fieldset></details>
  </li>;})}</ol>
  <p className="map-muted">Local presentation preview. Source records remain unchanged.</p>
 </aside>;
}
