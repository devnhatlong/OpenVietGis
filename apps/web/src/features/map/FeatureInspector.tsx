import type { SpatialFeatureDetail,SpatialLayer } from "@openvietgis/client-sdk";
import { formatFeatureValue } from "../spatial/feature-inspector";
export function FeatureInspector({layer,detail,focus,count,error}:{layer:SpatialLayer|undefined;detail:SpatialFeatureDetail|undefined;focus:string|null;count:number;error:string|null}) {
 const activeDetail=focus&&!error&&detail?detail:undefined;
 return <aside className="map-inspector" aria-label="Map feature inspector" data-testid="map-inspector" data-feature-id={activeDetail?.feature.feature_id}><h2>Inspector</h2>
 {!focus?<p>Select a feature on the active Layer or in the attribute table.</p>:error?<p role="alert">{error}</p>:!activeDetail?<p role="status">Checking selected feature access…</p>:<div>
 <h3>Feature {activeDetail.feature.feature_id}</h3><p>{count} selected{count>1?" · Focused feature shown":""}</p>
 <dl><dt>Layer</dt><dd>{layer?.name}</dd><dt>Source CRS</dt><dd>EPSG:{layer?.source.source_crs?.code??"unknown"}</dd><dt>Stored CRS</dt><dd>EPSG:{layer?.source.stored_crs?.code??"unknown"}</dd><dt>Response CRS</dt><dd>{activeDetail.context.response_crs?"EPSG:"+activeDetail.context.response_crs.code+" · X/Y":"Attributes only"}</dd><dt>Geometry state</dt><dd>{activeDetail.feature.geometry_state}</dd><dt>Content revision</dt><dd><code>{activeDetail.context.content_revision}</code></dd><dt>Schema revision</dt><dd><code>{activeDetail.context.schema_revision}</code></dd></dl>
 <table><thead><tr><th>Field / type</th><th>Exact value</th></tr></thead><tbody>{layer?.source.schema.fields.map(f=><tr key={f.field_id}><th>{f.name}<small>{f.field_id} · {f.type}</small></th><td><code>{formatFeatureValue(activeDetail.feature.attributes[f.field_id])}</code></td></tr>)}</tbody></table>
 {activeDetail.context.transformation?<p className="map-muted">Approved display operation {activeDetail.context.transformation.operation_id}. Native geometry remains unchanged.</p>:null}
 </div>}</aside>;
}
