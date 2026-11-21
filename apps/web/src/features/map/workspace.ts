import type { MapLayerReference, MapStyle, SpatialLayer, SpatialFeatureReadContext } from "@openvietgis/client-sdk";
import type { MapEngine, RenderLayer } from "./engine";

/** Do not retain the previous authorized frame while new protected reads settle. */
export function applyCurrentFrameSet(engine:Pick<MapEngine,"setLayers">|null, frames:RenderLayer[], busy:boolean):void {
 engine?.setLayers(busy?[]:frames);
}
export type Bounds = [number,number,number,number];
export interface SelectionScope { accountId:string; organizationId:string; projectId:string; layerId:string; sourceId:string; contentRevision:string; schemaRevision:string }
export const defaultStyle:MapStyle={color:"#2563eb",opacity:0.8,width:3,radius:6};
export const MAX_SELECTION=100;
export function selectionKey(scope:SelectionScope):string {return JSON.stringify([scope.accountId,scope.organizationId,scope.projectId,scope.layerId,scope.sourceId,scope.contentRevision,scope.schemaRevision]);}
export function toggleSelection(selected:readonly string[],id:string,multiple:boolean):string[] {
 if(!multiple)return [id];
 if(selected.includes(id))return selected.filter(value=>value!==id);
 return selected.length>=MAX_SELECTION?[...selected]:[...selected,id];
}
export function previewMove(layers:MapLayerReference[],id:string,direction:number):MapLayerReference[] {
 const from=layers.findIndex(l=>l.layer_id===id),to=from+direction;
 if(from<0||to<0||to>=layers.length)return layers;
 const result=[...layers];[result[from],result[to]]=[result[to]!,result[from]!];return result;
}
export function mapResponseMatches(org:string,project:string,value:{organization_id:string;project_id:string}):boolean{return value.organization_id===org&&value.project_id===project;}
export function viewportMatches(scope:SelectionScope,context:SpatialFeatureReadContext|{organization_id:string;project_id:string;layer_id:string;source_id:string;content_revision:string;schema_revision:string;geometry_included:boolean;response_crs:{authority:string;code:number;coordinate_order:string;unit:string;x_axis:string;y_axis:string}|null}):boolean {
 const crs=context.response_crs;
 return context.organization_id===scope.organizationId&&context.project_id===scope.projectId&&context.layer_id===scope.layerId&&context.source_id===scope.sourceId&&context.content_revision===scope.contentRevision&&context.schema_revision===scope.schemaRevision&&context.geometry_included&&crs?.authority==="EPSG"&&crs.code===4326&&crs.coordinate_order==="xy"&&crs.x_axis==="longitude"&&crs.y_axis==="latitude"&&crs.unit==="degree";
}
export function capability(layer:SpatialLayer|undefined,name:string):boolean {return Boolean(layer&&layer.lifecycle==="active"&&layer.source.lifecycle==="active"&&layer.capabilities.some(c=>c.name===name&&c.technical_supported&&c.available&&c.actor_authorized&&c.required_permission==="project.read"));}
export function boundsOfGeometry(geometry:{type:string;coordinates:unknown}|null|undefined):Bounds|null {
 if(!geometry)return null;
 let bounds:Bounds|null=null;
 function visit(value:unknown):void {
  if(!Array.isArray(value))return;
  if(value.length===2&&value.every(v=>typeof v==="number"&&Number.isFinite(v))) {
   const [x,y]=value as [number,number]; if(x < -180||x>180||y < -85.05112878||y>85.05112878)throw new Error("Unsupported display coordinate");
   bounds=bounds?[Math.min(bounds[0],x),Math.min(bounds[1],y),Math.max(bounds[2],x),Math.max(bounds[3],y)]:[x,y,x,y];
  }else for(const child of value)visit(child);
 }
 visit(geometry.coordinates);return bounds;
}
export function positionCount(value:unknown):number {if(!Array.isArray(value))return 0;if(value.length===2&&value.every(v=>typeof v==="number"))return 1;return value.reduce((sum:number,v)=>sum+positionCount(v),0);}
export function combineBounds(values:(Bounds|null)[]):Bounds|null {let result:Bounds|null=null;for(const value of values)if(value)result=result?[Math.min(result[0],value[0]),Math.min(result[1],value[1]),Math.max(result[2],value[2]),Math.max(result[3],value[3])]:[...value];return result;}
