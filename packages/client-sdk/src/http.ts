export interface ApiClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
  credentials?: RequestCredentials;
}

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly response: Response
  ) {
    super(`OpenVietGIS API request failed: ${status}`);
    this.name = "ApiError";
  }
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly credentials: RequestCredentials;
  private csrfToken: string | undefined;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch.bind(globalThis);
    this.credentials = options.credentials ?? "include";
  }

  setCsrfToken(token: string | undefined): void {
    this.csrfToken = token;
  }

  private async send(path: string, init?: RequestInit): Promise<Response> {
    const method = (init?.method ?? "GET").toUpperCase();
    const headers = new Headers(init?.headers);
    if (init?.body !== undefined && !(init.body instanceof FormData) && !headers.has("content-type")) {
      headers.set("content-type", "application/json");
    }
    if (UNSAFE_METHODS.has(method) && this.csrfToken && !headers.has("x-openvietgis-csrf")) {
      headers.set("x-openvietgis-csrf", this.csrfToken);
    }

    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      method,
      credentials: init?.credentials ?? this.credentials,
      headers
    });

    if (!response.ok) {
      throw new ApiError(response.status, response);
    }

    return response;
  }

  async requestWithoutBody(path: string, init?: RequestInit): Promise<void> {
    await this.send(path, init);
  }

  async requestRaw(path: string, init?: RequestInit): Promise<Response> {
    return this.send(path, init);
  }

  async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await this.send(path, init);
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }
}