import {
  Map as LibreMap,
  NavigationControl,
  setWorkerCount,
  setWorkerUrl,
  type GeoJSONSourceSpecification,
  type MapMouseEvent
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?url";
import type { MapStyle, MapViewpoint } from "@openvietgis/client-sdk";
import { isBasemapAvailable, type MapEngine, type MapEngineEvents, type RenderGeometry, type RenderLayer } from "./engine";
import { boundsOfGeometry, type Bounds } from "./workspace";
import { isImmutableViewportFeatures } from "./render-frame";

setWorkerUrl(workerUrl);
setWorkerCount(1);

const LAT = 85.05112878;
const gridFeatures: Array<{
  type: "Feature";
  properties: Record<string, never>;
  geometry: { type: "LineString"; coordinates: number[][] };
}> = [];
for (let longitude = -180; longitude <= 180; longitude += 30) {
  gridFeatures.push({
    type: "Feature",
    properties: {},
    geometry: {
      type: "LineString",
      coordinates: [
        [longitude, -LAT],
        [longitude, LAT]
      ]
    }
  });
}
for (let latitude = -60; latitude <= 60; latitude += 30) {
  gridFeatures.push({
    type: "Feature",
    properties: {},
    geometry: {
      type: "LineString",
      coordinates: [
        [-180, latitude],
        [180, latitude]
      ]
    }
  });
}

// Online raster sources are intentionally not constructed by this accepted grid-only profile.

/** The only renderer-specific boundary. No attributes or physical storage bindings enter it. */
export function createMapLibreEngine(container: HTMLElement, events: MapEngineEvents): MapEngine {
  const map = new LibreMap({
    container,
    attributionControl: false,
    renderWorldCopies: false,
    maxPitch: 60,
    fadeDuration: 0,
    keyboard: true,
    center: [105.84, 21.03],
    zoom: 5,
    style: {
      version: 8,
      sources: {
        "local-grid": {
          type: "geojson",
          data: { type: "FeatureCollection", features: gridFeatures }
        }
      },
      layers: [
        { id: "local-background", type: "background", paint: { "background-color": "#eef3f8" } },
        {
          id: "local-grid",
          type: "line",
          source: "local-grid",
          paint: { "line-color": "#cbd5e1", "line-width": 1 }
        }
      ]
    }
  });

  // Keep core map navigation available without leaking MapLibre controls into
  // business components. Keyboard, wheel and drag navigation stay enabled and
  // one visible control provides equivalent zoom/bearing actions.
  map.keyboard.enable();
  map.scrollZoom.enable();
  map.dragPan.enable();
  map.addControl(
    new NavigationControl({
      showCompass: true,
      showZoom: true,
      visualizePitch: true
    }),
    "bottom-right"
  );

  const zoomIn = container.querySelector<HTMLButtonElement>(
    ".maplibregl-ctrl-zoom-in"
  );
  const zoomOut = container.querySelector<HTMLButtonElement>(
    ".maplibregl-ctrl-zoom-out"
  );
  if (zoomIn) {
    zoomIn.title = "Phóng to bản đồ";
    zoomIn.setAttribute("aria-label", "Phóng to bản đồ");
  }
  if (zoomOut) {
    zoomOut.title = "Thu nhỏ bản đồ";
    zoomOut.setAttribute("aria-label", "Thu nhỏ bản đồ");
  }

  let layers: RenderLayer[] = [];
  let active: string | null = null;
  let selectedLayer: string | null = null;
  let selected: string[] = [];
  let loaded = false;
  let destroyed = false;
  // Native source IDs are never reused during this MapLibre instance: removing
  // a GeoJSON source sends an asynchronous worker request keyed by source ID.
  // Reusing a just-removed ID can interfere with its successor generation.
  let serial = 0;
  type Handle = {
    layer: string; source: string; logical: string; family: RenderGeometry["type"];
    signature: string; style: MapStyle;
  };
  let handles: Handle[] = [];
  // A module-owned immutable frame is independently validated by this adapter
  // the first time it is used. Repeated style/order renders can reuse the
  // resulting geometry signature; untrusted mutable arrays never qualify.
  const geometrySignatures = new WeakMap<RenderLayer["features"], { family: RenderGeometry["type"]; signature: string }>();

  function camera(): MapViewpoint {
    const center = map.getCenter();
    return {
      longitude: Math.max(-180, Math.min(180, center.lng)),
      latitude: Math.max(-LAT, Math.min(LAT, center.lat)),
      zoom: map.getZoom(),
      bearing: map.getBearing(),
      pitch: map.getPitch(),
      crs: 4326
    };
  }

  function settle(): void {
    if (destroyed) return;
    const b = map.getBounds();
    const west = Math.max(-180, b.getWest());
    const east = Math.min(180, b.getEast());
    const south = Math.max(-LAT, b.getSouth());
    const north = Math.min(LAT, b.getNorth());
    if (west < east && south < north) events.viewport([west, south, east, north], camera());
  }

  function selectedColor(logical: string, color: string): unknown {
    return selectedLayer === logical && selected.length
      ? ["case", ["in", ["get", "feature_id"], ["literal", selected]], "#f59e0b", color]
      : color;
  }

  function applyBasemap(): void {
    if (!loaded || destroyed) return;
    // Local grid only: no third-party URL or raster source can be constructed
    // by this adapter until a separately approved basemap profile is added.
    if (map.getLayer("local-grid"))
      map.setLayoutProperty("local-grid", "visibility", "visible");
    map.triggerRepaint();
  }

  const sameStyle = (a:MapStyle,b:MapStyle) =>
    a.color===b.color&&a.opacity===b.opacity&&a.width===b.width&&a.radius===b.radius;

  function colorProperty(family:RenderGeometry["type"]):"circle-color"|"line-color"|"fill-color" {
    return family==="Point"?"circle-color":family==="LineString"?"line-color":"fill-color";
  }

  function removeHandle(handle:Handle):void {
    if(map.getLayer(handle.layer))map.removeLayer(handle.layer);
    if(map.getSource(handle.source))map.removeSource(handle.source);
  }

  function updatePaint(handle:Handle, style:MapStyle):void {
    if(handle.style.color!==style.color)
      map.setPaintProperty(handle.layer,colorProperty(handle.family),selectedColor(handle.logical,style.color) as string);
    if(handle.family==="Point"){
      if(handle.style.radius!==style.radius)map.setPaintProperty(handle.layer,"circle-radius",style.radius);
      if(handle.style.opacity!==style.opacity)map.setPaintProperty(handle.layer,"circle-opacity",style.opacity);
    }else if(handle.family==="LineString"){
      if(handle.style.width!==style.width)map.setPaintProperty(handle.layer,"line-width",style.width);
      if(handle.style.opacity!==style.opacity)map.setPaintProperty(handle.layer,"line-opacity",style.opacity);
    }else if(handle.style.opacity!==style.opacity){
      map.setPaintProperty(handle.layer,"fill-opacity",style.opacity);
    }
    handle.style={...style};
  }

  function createHandle(layer:RenderLayer,family:RenderGeometry["type"],signature:string,before?:Handle):Handle {
    const generation=++serial,source="project-data-"+generation,id="project-layer-"+generation;
    const features=layer.features.map(item=>({
      type:"Feature",id:item.feature_id,properties:{feature_id:item.feature_id},geometry:item.geometry
    }));
    const handle:Handle={layer:id,source,logical:layer.id,family,signature,style:{...layer.style}};
    // Register before mutation so the fail-closed cleanup also covers partial creation.
    handles.splice(before ? handles.indexOf(before) : handles.length,0,handle);
    map.addSource(source,{type:"geojson",data:{type:"FeatureCollection",features} as GeoJSONSourceSpecification["data"]});
    const color=selectedColor(layer.id,layer.style.color) as string;
    if(family==="Point"){
      map.addLayer({id,source,type:"circle",paint:{
        "circle-color":color,"circle-radius":layer.style.radius,"circle-opacity":layer.style.opacity,
        "circle-stroke-color":"#ffffff","circle-stroke-width":2
      }},before?.layer);
    }else if(family==="LineString"){
      map.addLayer({id,source,type:"line",paint:{
        "line-color":color,"line-width":layer.style.width,"line-opacity":layer.style.opacity
      }},before?.layer);
    }else{
      map.addLayer({id,source,type:"fill",paint:{
        "fill-color":color,"fill-opacity":layer.style.opacity,"fill-outline-color":"#1e293b"
      }},before?.layer);
    }
    return handle;
  }

  function apply(): void {
    if (!loaded || destroyed) return;
    try {
      // The tree is top-to-bottom; the native style stack is bottom-to-top.
      // Only exact, currently authorized geometry + pins may keep a handle.
      const seen=new Set<string>();
      const desired=[...layers].reverse().flatMap(layer=>{
        if(seen.has(layer.id)||!layer.scopeKey)throw new Error("Invalid render scope");
        seen.add(layer.id);
        if(!layer.features.length)return [];
        let geometry=geometrySignatures.get(layer.features);
        if(!geometry){
          const family=layer.features[0]!.geometry.type;
          for(const item of layer.features){
            if(item.geometry.type!==family||!boundsOfGeometry(item.geometry))
              throw new Error("Invalid render geometry");
          }
          geometry={family,signature:JSON.stringify(layer.features)};
          if(isImmutableViewportFeatures(layer.features))geometrySignatures.set(layer.features,geometry);
        }
        return [{layer,family:geometry.family,signature:JSON.stringify(layer.scopeKey)+":"+geometry.signature}];
      });
      const prior=new Map(handles.map(h=>[h.logical,h]));
      const desiredById=new Map(desired.map(frame=>[frame.layer.id,frame]));
      const remove=handles.filter(h=>desiredById.get(h.logical)?.signature!==h.signature);
      const changedOrder=handles.map(h=>h.logical).join("\u0000")!==desired.map(f=>f.layer.id).join("\u0000");
      const changedSource=desired.some(f=>prior.get(f.layer.id)?.signature!==f.signature);
      const changedPaint=desired.some(f=>{
        const h=prior.get(f.layer.id);return h&&!sameStyle(h.style,f.layer.style);
      });
      // Identical current frames do not invalidate idle or schedule worker work.
      if(!remove.length&&!changedOrder&&!changedSource&&!changedPaint)return;
      events.ready(false);
      for(const handle of remove){removeHandle(handle);prior.delete(handle.logical);}
      handles=handles.filter(handle=>prior.has(handle.logical));
      const next:Handle[]=[];
      for(const [index,f] of desired.entries()){
        const existing=prior.get(f.layer.id);
        if(existing){
          updatePaint(existing,f.layer.style);
          next.push(existing);
        }else{
          // Install a new/replacement source directly below its next surviving
          // logical successor. On the first open there are no successors, so
          // additions alone establish the exact draw order.
          const before=desired.slice(index+1).map(candidate=>prior.get(candidate.layer.id)).find(Boolean);
          next.push(createHandle(f.layer,f.family,f.signature,before));
        }
      }
      // Only actual arrangement differences require native moveLayer calls.
      // Repeated unconditional moves cause redundant style/worker updates
      // even when sources were added in the correct order initially.
      const physicalOrder=handles.map(handle=>handle.layer);
      for(let index=next.length-1; index>=0; index--){
        const id=next[index]!.layer,before=next[index+1]?.layer,from=physicalOrder.indexOf(id);
        if(physicalOrder[from+1]===before)continue;
        map.moveLayer(id,before);
        physicalOrder.splice(from,1);
        physicalOrder.splice(before===undefined?physicalOrder.length:physicalOrder.indexOf(before),0,id);
      }
      handles=next;
      map.triggerRepaint();
    }catch{
      events.ready(false);
      for(const handle of handles)removeHandle(handle);
      handles=[];
      events.error();
    }
  }

  function pick(event: MapMouseEvent): void {
    const target = handles.find((h) => h.logical === active);
    if (!target) return;
    const ids = map
      .queryRenderedFeatures(event.point, { layers: [target.layer] })
      .map((f) => f.properties?.feature_id)
      .filter((id): id is string => typeof id === "string")
      .sort();
    if (ids[0]) {
      events.pick(
        ids[0],
        event.originalEvent.shiftKey || event.originalEvent.ctrlKey || event.originalEvent.metaKey
      );
    }
  }

  map.on("load", () => {
    if (destroyed) return;
    loaded = true;
    applyBasemap();
    apply();
    settle();
  });
  map.on("click", pick);
  map.on("moveend", settle);
  map.on("idle", () => {
    if (!destroyed) events.ready(true);
  });
  map.on("error", () => {
    if (!destroyed) {
      events.ready(false);
      events.error();
    }
  });
  const observer = new ResizeObserver(() => {
    if (!destroyed) map.resize();
  });
  observer.observe(container);

  return {
    setBasemap(id) {
      // A direct or stale UI invocation cannot enable unapproved online tiles.
      if (isBasemapAvailable(id)) applyBasemap();
    },
    setLayers(value) {
      layers = value;
      apply();
    },
    setActiveLayer(value) {
      active = value;
    },
    setSelection(layerId, ids) {
      if (selectedLayer === layerId && selected.join("\u0000") === ids.join("\u0000")) return;
      const affectedLayers=new Set([
        ...(selected.length&&selectedLayer?[selectedLayer]:[]),
        ...(ids.length&&layerId?[layerId]:[])
      ]);
      selectedLayer=layerId;
      selected=[...ids];
      if(!loaded||destroyed)return;
      const affected=[...affectedLayers].flatMap(id=>handles.filter(h=>h.logical===id));
      if(!affected.length)return;
      events.ready(false);
      // Highlight changes alter paint only, not any GeoJSON source or tile index.
      for(const handle of affected)
        map.setPaintProperty(handle.layer,colorProperty(handle.family),selectedColor(handle.logical,handle.style.color) as string);
      map.triggerRepaint();
    },
    setCamera(value) {
      map.jumpTo({
        center: [value.longitude, value.latitude],
        zoom: value.zoom,
        bearing: value.bearing,
        pitch: value.pitch
      });
      settle();
    },
    getCamera: camera,
    fitBounds(value: Bounds) {
      const [w, s, e, n] = value;
      const target = map.cameraForBounds(
        [
          [w, s],
          [e, n]
        ],
        { padding: 48, maxZoom: 18 }
      );
      if (!target) return;
      map.jumpTo({
        ...(target.center ? { center: target.center } : {}),
        ...(typeof target.zoom === "number" ? { zoom: target.zoom } : {}),
        ...(typeof target.bearing === "number" ? { bearing: target.bearing } : {}),
        ...(typeof target.pitch === "number" ? { pitch: target.pitch } : {})
      });
      // Publish the exact resulting viewport synchronously. Relying only on
      // MapLibre's moveend after fitBounds can lag behind repeated renderer
      // lifecycles and leave protected viewport queries pinned to stale bounds.
      settle();
    },
    zoom(delta) {
      map.zoomTo(Math.max(0, Math.min(22, map.getZoom() + delta)), { duration: 0 });
    },
    clear() {
      layers = [];
      active = null;
      selectedLayer = null;
      selected = [];
      apply();
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      observer.disconnect();
      map.remove();
    }
  };
}
