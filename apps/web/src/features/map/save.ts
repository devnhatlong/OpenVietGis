import type { SaveMapInput,MapSaveReceipt } from "@openvietgis/client-sdk";
export type SaveStatus="dirty"|"saving"|"unresolved"|"committed"|"conflict"|"denied"|"failed";
export interface PendingSave {input:SaveMapInput;status:SaveStatus}
export function beginSave(input:SaveMapInput):PendingSave{return {input,status:"saving"};}
export function markUnresolved(pending:PendingSave):PendingSave{return {...pending,status:"unresolved"};}
export function receiptMatches(pending:PendingSave,receipt:MapSaveReceipt):boolean{return pending.input.operation_id===receipt.operation_id&&Number.isSafeInteger(receipt.configuration_revision)&&receipt.configuration_revision>pending.input.expected_revision;}
export function saveErrorState(status:number|undefined):SaveStatus {
 if(status===409)return "conflict";
 if(status!==undefined&&[401,403,404].includes(status))return "denied";
 if(status!==undefined&&status>=400&&status<500)return "failed";
 return "unresolved";
}
