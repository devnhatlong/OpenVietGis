import { describe,expect,it } from "vitest";
import { beginSave, markUnresolved, receiptMatches, saveErrorState } from "./save";
describe("explicit save recovery",()=>{
  const input={operation_id:"op",expected_revision:2,layers:[],basemap:"grid" as const,default_viewpoint:{mode:"preserve" as const}};
  it("retains exact operation and intent through ambiguous transport and retries",()=>{
    const pending=beginSave(input); const unknown=markUnresolved(pending);
    expect(unknown.input).toBe(input); expect(unknown.status).toBe("unresolved");
    expect(receiptMatches(unknown,{map_id:"m",operation_id:"other",configuration_revision:3})).toBe(false);
    expect(receiptMatches(unknown,{map_id:"m",operation_id:"op",configuration_revision:3})).toBe(true);
  });
  it("never transforms conflicts or denial into a fresh retry",()=>{
    expect(saveErrorState(409)).toBe("conflict");expect(saveErrorState(403)).toBe("denied");expect(saveErrorState(503)).toBe("unresolved");
  });
});
