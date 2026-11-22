import { useRef,useState } from "react";
import { invokeCommand,type MapCommand } from "./commands";
export function CommandBar({commands}:{commands:MapCommand[]}) {
 const [search,setSearch]=useState("");
 const searchMenu=useRef<HTMLDetailsElement>(null);
 function executeSearch(id:string):void {
  if(!invokeCommand(commands,id,"search"))return;
  if(searchMenu.current){searchMenu.current.open=false;searchMenu.current.querySelector("summary")?.focus();}
 }
 return <nav className="map-commandbar" aria-label="Lệnh bản đồ">
  <div className="map-primary-tools">{commands.filter(c=>["map.add-data","map.fit-layer","map.fit-all","map.fit-selection","map.clear-selection","map.zoom-in","map.zoom-out","map.save"].includes(c.id)).map(c=><button key={c.id} type="button" disabled={!c.enabled} title={c.reason??c.label} onClick={()=>invokeCommand(commands,c.id,"toolbar")}>{c.label}</button>)}</div>
  <details ref={searchMenu} className="map-command-search"><summary>Tìm nhanh lệnh</summary><label>Tìm lệnh bản đồ <input aria-label="Tìm lệnh bản đồ" value={search} onChange={e=>setSearch(e.target.value)}/></label>
   <ul>{commands.filter(c=>c.label.toLowerCase().includes(search.toLowerCase())).map(c=><li key={c.id}><button type="button" disabled={!c.enabled} title={c.reason??c.label} onClick={()=>executeSearch(c.id)}>{c.label}</button>{!c.enabled?<small>{c.reason}</small>:null}</li>)}</ul>
  </details>
 </nav>;
}
