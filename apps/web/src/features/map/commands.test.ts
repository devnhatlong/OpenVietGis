import { describe,expect,it,vi } from "vitest";
import { createCommands, invokeCommand } from "./commands";
describe("map command registry",()=>{
  it("shares execution and availability across every UI entry point",()=>{
    const run=vi.fn(); const commands=createCommands({hasActive:true,hasVisible:true,hasSelection:true,canSave:true,busy:false},run);
    for(const entry of ["toolbar","context","search","shortcut"] as const) expect(invokeCommand(commands,"map.fit-layer",entry)).toBe(true);
    expect(run).toHaveBeenCalledTimes(4);
    expect(run.mock.calls.every(c=>c[0]==="map.fit-layer")).toBe(true);
  });
  it("separates current permission from technical capability and blocks unknown operations",()=>{
    const run=vi.fn();const commands=createCommands({hasActive:false,hasVisible:false,hasSelection:false,canSave:false,busy:false},run);
    expect(invokeCommand(commands,"map.save","shortcut")).toBe(false);
    expect(invokeCommand(commands,"map.edit","search")).toBe(false);
    expect(commands.find(c=>c.id==="map.save")?.reason).toContain("project.edit");
    expect(run).not.toHaveBeenCalled();
  });
});
