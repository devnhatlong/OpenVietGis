export type MapCommandId="map.fit-layer"|"map.fit-all"|"map.fit-selection"|"map.clear-selection"|"map.save"|"map.set-default-viewpoint"|"map.zoom-in"|"map.zoom-out";
export type EntryPoint="toolbar"|"context"|"search"|"shortcut";
export interface MapCommand {id:MapCommandId;label:string;enabled:boolean;reason:string|null;execute:()=>void}
export interface CommandContext {hasActive:boolean;hasVisible:boolean;hasSelection:boolean;canSave:boolean;busy:boolean}
export function createCommands(context:CommandContext,run:(id:MapCommandId)=>void):MapCommand[] {
 const definitions:[MapCommandId,string,boolean,string][]=[
 ["map.fit-layer","Fit active Layer",context.hasActive,"Choose a render-compatible active Layer."],
 ["map.fit-all","Fit visible Layers",context.hasVisible,"Add a visible render-compatible Layer."],
 ["map.fit-selection","Zoom to selection",context.hasSelection,"Select readable features with available geometry."],
 ["map.clear-selection","Clear selection",context.hasSelection,"No selected features."],
 ["map.save","Save map",context.canSave,"Current project.edit authority is required."],
 ["map.set-default-viewpoint","Set default viewpoint",context.canSave,"Current project.edit authority is required."],
 ["map.zoom-in","Zoom in",true,""],["map.zoom-out","Zoom out",true,""]];
 return definitions.map(([id,label,enabled,reason])=>({id,label,enabled:enabled&&!context.busy,reason:context.busy?"An operation is in progress.":enabled?null:reason,execute:()=>run(id)}));
}
export function invokeCommand(commands:MapCommand[],id:string,_entry:EntryPoint):boolean {void _entry;const command=commands.find(c=>c.id===id);if(!command?.enabled)return false;command.execute();return true;}
