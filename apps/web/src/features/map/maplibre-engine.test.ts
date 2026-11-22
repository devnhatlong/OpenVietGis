import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BASEMAP_OPTIONS, isBasemapAvailable, LOCAL_BASEMAP, ONLINE_BASEMAP_UNAVAILABLE, type RenderLayer, type MapEngine } from "./engine";
import { createMapLibreEngine } from "./maplibre-engine";

const fake = vi.hoisted(() => {
  const handlers = new Map<string, () => void>();
  const sources = new Set<string>();
  const layerIds: string[] = [];
  const addSource = vi.fn((id:string) => { if (sources.has(id)) throw new Error("duplicate source"); sources.add(id); });
  const removeSource = vi.fn((id:string) => { if (!sources.delete(id)) throw new Error("missing source"); });
  const addLayer = vi.fn((definition:{id:string}, before?:string) => {
    if(layerIds.includes(definition.id)) throw new Error("duplicate layer");
    layerIds.splice(before ? layerIds.indexOf(before) : layerIds.length,0,definition.id);
  });
  const removeLayer = vi.fn((id:string) => { const index=layerIds.indexOf(id); if(index<0)throw new Error("missing layer"); layerIds.splice(index,1); });
  const moveLayer = vi.fn((id:string,before?:string) => { const index=layerIds.indexOf(id); if(index<0)throw new Error("missing layer"); layerIds.splice(index,1);layerIds.splice(before?layerIds.indexOf(before):layerIds.length,0,id); });
  const map = {
    keyboard:{enable:vi.fn()},scrollZoom:{enable:vi.fn()},dragPan:{enable:vi.fn()},addControl:vi.fn(),
    on:vi.fn((event:string, fn:()=>void)=>{handlers.set(event,fn);}),
    addSource,removeSource,addLayer,removeLayer,moveLayer,
    getLayer:vi.fn((id:string)=>layerIds.includes(id)?{id}:undefined),
    getSource:vi.fn((id:string)=>sources.has(id)?{id}:undefined),
    setLayoutProperty:vi.fn(),setPaintProperty:vi.fn(),triggerRepaint:vi.fn(),
    getCenter:vi.fn(()=>({lng:0,lat:0})),getZoom:vi.fn(()=>1),getBearing:vi.fn(()=>0),getPitch:vi.fn(()=>0),
    getBounds:vi.fn(()=>({getWest:()=>-1,getEast:()=>1,getSouth:()=>-1,getNorth:()=>1})),
    resize:vi.fn(),remove:vi.fn(),
    queryRenderedFeatures:vi.fn(()=>[{properties:{feature_id:"point-000001"}}])
  };
  return {map,handlers,sources,layerIds,addSource,removeSource,addLayer,removeLayer,moveLayer};
});
vi.mock("maplibre-gl",()=>({
  Map:vi.fn(function(){return fake.map;}),
  NavigationControl:vi.fn(function(){}),setWorkerCount:vi.fn(),setWorkerUrl:vi.fn()
}));

const style={color:"#2563eb",opacity:.8,width:2,radius:6};
const point=(id:string,x=105):RenderLayer=>({id,scopeKey:id+"-pin",style:{...style},features:[{feature_id:"point-000001",geometry:{type:"Point",coordinates:[x,10]}}]});
const line=(id:string):RenderLayer=>({id,scopeKey:id+"-pin",style:{...style},features:[{feature_id:"line-000001",geometry:{type:"LineString",coordinates:[[105,10],[106,11]]}}]});
const polygon=(id:string):RenderLayer=>({id,scopeKey:id+"-pin",style:{...style},features:[{feature_id:"polygon-000001",geometry:{type:"Polygon",coordinates:[[[105,10],[106,10],[106,11],[105,10]]]}}]});

describe("MapLibre renderer invalidation and bounded work",()=>{
  let engine:MapEngine;
  const ready=vi.fn();
  beforeEach(()=>{
    vi.clearAllMocks();
    fake.handlers.clear();fake.sources.clear();fake.layerIds.splice(0);
    vi.stubGlobal("ResizeObserver",class {observe(){} disconnect(){}});
    engine=createMapLibreEngine({querySelector:()=>null} as unknown as HTMLElement,{
      viewport:vi.fn(),pick:vi.fn(),ready,error:vi.fn()
    });
    fake.handlers.get("load")?.();
    ready.mockClear();
  });
  afterEach(()=>{engine.destroy();vi.unstubAllGlobals();});

  it("permits only the local grid and cannot construct remote raster sources even through a direct adapter call",()=>{
    expect(LOCAL_BASEMAP).toBe("grid");
    expect(BASEMAP_OPTIONS.filter(option=>option.available).map(option=>option.id)).toEqual(["grid"]);
    expect(ONLINE_BASEMAP_UNAVAILABLE).toContain("chưa được cấu hình/phê duyệt");
    for(const option of BASEMAP_OPTIONS.filter(option=>option.id!=="grid")){
      expect(isBasemapAvailable(option.id)).toBe(false);
      engine.setBasemap(option.id);
    }
    expect(fake.addSource).not.toHaveBeenCalled();
    // A call before native load must not store an unapproved provider for
    // the load callback to activate later either.
    engine.destroy();
    engine=createMapLibreEngine({querySelector:()=>null} as unknown as HTMLElement,{
      viewport:vi.fn(),pick:vi.fn(),ready,error:vi.fn()
    });
    engine.setBasemap("google-hybrid");
    fake.handlers.get("load")?.();
    expect(fake.addSource).not.toHaveBeenCalled();
    engine.setLayers([point("p")]);
    expect(fake.addSource).toHaveBeenCalledTimes(1);
    expect(fake.addSource).toHaveBeenCalledWith(expect.stringMatching(/^project-data-/),expect.objectContaining({type:"geojson"}));
  });

  it("loads three geometry sources once and leaves an identical settled frame alone",()=>{
    engine.setLayers([point("p"),line("l"),polygon("a")]);
    expect(fake.addSource).toHaveBeenCalledTimes(3);
    expect(ready).toHaveBeenLastCalledWith(false);
    fake.handlers.get("idle")?.();
    expect(ready).toHaveBeenLastCalledWith(true);
    ready.mockClear();
    engine.setLayers([point("p"),line("l"),polygon("a")]);
    expect(fake.addSource).toHaveBeenCalledTimes(3);
    expect(fake.removeSource).not.toHaveBeenCalled();
    expect(ready).not.toHaveBeenCalled();
  });

  it("installs all three sources directly in exact draw order, without redundant moves",()=>{
    engine.setLayers([point("p"),line("l"),polygon("a")]);
    expect(fake.layerIds).toEqual(["project-layer-1","project-layer-2","project-layer-3"]);
    expect(fake.moveLayer).not.toHaveBeenCalled();
    // Replacing a middle source with a fresh generation must insert at its
    // existing draw position, not append and reshuffle every stable layer.
    const changedLine=line("l");
    changedLine.features[0]!.geometry.coordinates=[[105,10],[107,11]];
    engine.setLayers([point("p"),changedLine,polygon("a")]);
    expect(fake.layerIds).toEqual(["project-layer-1","project-layer-4","project-layer-3"]);
    expect(fake.moveLayer).not.toHaveBeenCalled();
    expect(fake.addSource).toHaveBeenCalledTimes(4);
    expect(fake.removeSource).toHaveBeenCalledTimes(1);
  });

  it("detects in-place changes to untrusted mutable inputs rather than assuming identity is safe",()=>{
    const p=point("p");
    engine.setLayers([p]);
    p.features[0]!.geometry.coordinates=[106,10];
    engine.setLayers([p]);
    expect(fake.addSource).toHaveBeenCalledTimes(2);
    expect(fake.removeSource).toHaveBeenCalledTimes(1);
    // Same coordinates under a different pinned scope are a new generation.
    engine.setLayers([{...p,scopeKey:"new-authorized-pin"}]);
    expect(fake.addSource).toHaveBeenCalledTimes(3);
    expect(fake.removeSource).toHaveBeenCalledTimes(2);
  });

  it("updates selected/cleared feature paint without reparsing any geometry source",()=>{
    engine.setLayers([point("p"),line("l"),polygon("a")]);
    engine.setSelection("p",["point-000001"]);
    expect(fake.addSource).toHaveBeenCalledTimes(3);
    expect(fake.removeSource).not.toHaveBeenCalled();
    expect(fake.map.setPaintProperty).toHaveBeenLastCalledWith(expect.any(String),"circle-color",expect.arrayContaining(["#f59e0b"]));
    engine.setSelection("l",["line-000001"]);
    expect(fake.map.setPaintProperty).toHaveBeenCalledWith(expect.any(String),"circle-color",style.color);
    expect(fake.map.setPaintProperty).toHaveBeenLastCalledWith(expect.any(String),"line-color",expect.arrayContaining(["#f59e0b"]));
    engine.setSelection(null,[]);
    expect(fake.map.setPaintProperty).toHaveBeenLastCalledWith(expect.any(String),"line-color",style.color);
    expect(fake.addSource).toHaveBeenCalledTimes(3);
  });

  it("moves layers, changes style and removes an absent layer without rebuilding unrelated sources",()=>{
    const p=point("p"),l=line("l"),a=polygon("a");
    engine.setLayers([p,l,a]);
    const oldSources=[...fake.sources];
    engine.setLayers([a,{...p,style:{...p.style,color:"#334455"}},l]);
    expect(fake.addSource).toHaveBeenCalledTimes(3);
    expect(fake.removeSource).not.toHaveBeenCalled();
    expect(fake.moveLayer).toHaveBeenCalled();
    expect(fake.map.setPaintProperty).toHaveBeenCalledWith(expect.any(String),"circle-color","#334455");
    engine.setLayers([a,l]);
    expect(fake.removeSource).toHaveBeenCalledTimes(1);
    expect(fake.addSource).toHaveBeenCalledTimes(3);
    expect([...fake.sources].every(id=>oldSources.includes(id))).toBe(true);
  });

  it("replaces only a changed geometry, uses a fresh physical handle, then discards every source on clear",()=>{
    engine.setLayers([point("p"),line("l"),polygon("a")]);
    const oldIds=[...fake.sources];
    engine.setLayers([point("p",106),line("l"),polygon("a")]);
    expect(fake.removeSource).toHaveBeenCalledTimes(1);
    expect(fake.addSource).toHaveBeenCalledTimes(4);
    expect([...fake.sources].filter(id=>oldIds.includes(id))).toHaveLength(2);
    engine.setLayers([]);
    expect(fake.sources.size).toBe(0);
    expect(fake.layerIds).toHaveLength(0);
    expect(ready).toHaveBeenLastCalledWith(false);
    fake.handlers.get("idle")?.();
    expect(ready).toHaveBeenLastCalledWith(true);
  });
});
