import { ApiClient, ApiError, loadCsrfToken } from "@openvietgis/client-sdk";

export const hnClient = new ApiClient({ baseUrl: "/api/v1" });

export async function withCsrf<T>(action: () => Promise<T>): Promise<T> {
  await loadCsrfToken(hnClient);
  return action();
}

export async function uiError(error: unknown): Promise<string> {
  if (error instanceof ApiError) {
    try {
      const payload = (await error.response.json()) as { message?: string; detail?: string; code?: string };
      return payload.message ?? payload.detail ?? payload.code ?? `HTTP ${error.status}`;
    } catch {
      return `HTTP ${error.status}`;
    }
  }
  return error instanceof Error ? error.message : "Thao tác không thành công.";
}
