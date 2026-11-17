import { ApiClient } from "./http";

export type ReadyResponse =
  | { status: "ready"; database: "ready" }
  | { status: "not_ready"; database: "unavailable" };

export interface LiveResponse {
  status: "ok";
}

export function getLiveness(client: ApiClient): Promise<LiveResponse> {
  return client.request<LiveResponse>("/health/live");
}

export function getReadiness(client: ApiClient): Promise<ReadyResponse> {
  return client.request<ReadyResponse>("/health/ready");
}
