import { describe, expect, it } from "vitest";
import { applyCurrentFrameSet, boundsOfGeometry, combineBounds, defaultStyle, mapResponseMatches, previewMove, selectionKey, toggleSelection, viewportMatches } from "./workspace";
import type { RenderLayer } from "./engine";

describe("map workspace invariants", () => {
  const scope = { accountId:"a",organizationId:"o",projectId:"p",layerId:"l",sourceId:"s",contentRevision:"c",schemaRevision:"r" };
  it("clears previously authorized render buffers while any protected viewport is loading", () => {
    const prior:RenderLayer={id:"revoked",scopeKey:"revoked-pin",style:defaultStyle,features:[{feature_id:"private",geometry:{type:"Point",coordinates:[105,10]}}]};
    const current:RenderLayer={id:"current",scopeKey:"current-pin",style:defaultStyle,features:[{feature_id:"public",geometry:{type:"Point",coordinates:[106,11]}}]};
    let rendered:RenderLayer[]=[];
    const engine={setLayers:(layers:RenderLayer[])=>{rendered=layers;}};
    applyCurrentFrameSet(engine,[prior,current],false);
    expect(rendered).toEqual([prior,current]);
    // A revoked layer and another in-flight layer must not leave a retained frame.
    applyCurrentFrameSet(engine,[current],true);
    expect(rendered).toEqual([]);
    // Once the current protected reads settle, only their verified frame is sent.
    applyCurrentFrameSet(engine,[current],false);
    expect(rendered).toEqual([current]);
    applyCurrentFrameSet(engine,[],false);
    expect(rendered).toEqual([]);
  });
  it("binds selections to actor, tenant, logical layer, source and independent pins", () => {
    const keys = ["accountId","organizationId","projectId","layerId","sourceId","contentRevision","schemaRevision"] as const;
    for (const key of keys) expect(selectionKey({...scope,[key]:"other"})).not.toBe(selectionKey(scope));
  });
  it("retains selected IDs across pages, caps at100 and toggles without substitution", () => {
    let ids:string[]=[];
    for(let i=0;i<100;i++) ids=toggleSelection(ids,String(i),true);
    expect(toggleSelection(ids,"overflow",true)).toEqual(ids);
    expect(toggleSelection(ids,"3",true)).not.toContain("3");
    expect(toggleSelection(ids,"focused",false)).toEqual(["focused"]);
  });
  it("reorders logical references without changing source objects", () => {
    const a={layer_id:"a",visible:true,style:defaultStyle}, b={layer_id:"b",visible:false,style:defaultStyle};
    expect(previewMove([a,b],"b",-1)).toEqual([b,a]); expect(a).toEqual({layer_id:"a",visible:true,style:defaultStyle});
    expect(previewMove([a,b],"a",-1)).toEqual([a,b]);
  });
  it("uses actual vertices for selected bounds and never invents empty geometry", () => {
    expect(boundsOfGeometry({type:"Polygon",coordinates:[[[105,10],[106,10],[105,12],[105,10]]]})).toEqual([105,10,106,12]);
    expect(boundsOfGeometry({type:"Point",coordinates:[]})).toBeNull();
    expect(combineBounds([null,[1,2,3,4],[0,5,6,7]])).toEqual([0,2,6,7]);
  });
  it("rejects delayed scope/pin responses and native geometry pretending to be4326", () => {
    const context={organization_id:"o",project_id:"p",layer_id:"l",source_id:"s",content_revision:"c",schema_revision:"r",geometry_included:true,response_crs:{authority:"EPSG",code:4326,coordinate_order:"xy",unit:"degree",x_axis:"longitude",y_axis:"latitude"},transformation:null};
    expect(viewportMatches(scope,context)).toBe(true);
    for(const key of ["organization_id","project_id","layer_id","source_id","content_revision","schema_revision"] as const)
      expect(viewportMatches(scope,{...context,[key]:"foreign"})).toBe(false);
    expect(viewportMatches(scope,{...context,response_crs:{...context.response_crs,code:5899}})).toBe(false);
    expect(mapResponseMatches("o","p",{organization_id:"other",project_id:"p"})).toBe(false);
  });
});
