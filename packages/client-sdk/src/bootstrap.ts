import type { operations } from "./generated/service-admin";
import { ApiClient } from "./http";

export type BootstrapStatus =
  operations["getBootstrapStatus"]["responses"][200]["content"]["application/json"];
export type BootstrapInput =
  operations["initializeInstallation"]["requestBody"]["content"]["application/json"];
export type BootstrapResult =
  operations["initializeInstallation"]["responses"][201]["content"]["application/json"];

export function getBootstrapStatus(client: ApiClient): Promise<BootstrapStatus> {
  return client.request<BootstrapStatus>("/bootstrap/status");
}

export function initializeInstallation(
  client: ApiClient,
  input: BootstrapInput,
  authority: string
): Promise<BootstrapResult> {
  return client.request<BootstrapResult>("/bootstrap/initialize", {
    method: "POST",
    headers: { Authorization: "Bearer " + authority },
    body: JSON.stringify(input)
  });
}
