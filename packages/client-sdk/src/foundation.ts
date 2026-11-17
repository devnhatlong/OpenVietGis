import { ApiClient } from "./http";

export interface FoundationRecord {
  id: string;
  label: string;
  created_at: string;
  updated_at: string;
}

export interface FoundationRecordCreate {
  label: string;
}

export function createFoundationRecord(
  client: ApiClient,
  input: FoundationRecordCreate
): Promise<FoundationRecord> {
  return client.request<FoundationRecord>("/foundation-records", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function getFoundationRecord(client: ApiClient, id: string): Promise<FoundationRecord> {
  return client.request<FoundationRecord>(`/foundation-records/${encodeURIComponent(id)}`);
}
