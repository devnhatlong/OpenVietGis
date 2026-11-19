import type { MapStyle,MapViewpoint } from "@openvietgis/client-sdk";
import type { Bounds } from "./workspace";
export interface RenderGeometry {type:"Point"|"LineString"|"Polygon";coordinates:unknown}
export interface RenderFeature {feature_id:string;geometry:RenderGeometry}
export interface RenderLayer {id:string;style:MapStyle;features:RenderFeature[]}
export interface MapEngineEvents {viewport:(bounds:Bounds,camera:MapViewpoint)=>void;pick:(id:string,multiple:boolean)=>void;ready:(ready:boolean)=>void;error:()=>void}
export interface MapEngine {setLayers(layers:RenderLayer[]):void;setActiveLayer(id:string|null):void;setSelection(layerId:string|null,ids:string[]):void;setCamera(camera:MapViewpoint):void;getCamera():MapViewpoint;fitBounds(bounds:Bounds):void;zoom(delta:number):void;clear():void;destroy():void}
