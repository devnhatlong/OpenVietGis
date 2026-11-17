import { describe, expect, it } from "vitest";

import { ApiClient, createFoundationRecord, getFoundationRecord } from "../src";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" }
  });
}

describe("foundation client", () => {
  it("creates a record through the configured base URL", async () => {
    const calls: Array<{ url: string; init: RequestInit | undefined }> = [];
    const fetchImpl = async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init });
      return jsonResponse(
        {
          id: "00000000-0000-0000-0000-000000000001",
          label: "client-check",
          created_at: "2026-11-17T00:00:00Z",
          updated_at: "2026-11-17T00:00:00Z"
        },
        201
      );
    };

    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1/",
      fetchImpl: fetchImpl as typeof fetch
    });

    const record = await createFoundationRecord(client, { label: "client-check" });

    expect(record.label).toBe("client-check");
    expect(calls[0]?.url).toBe("http://example.test/api/v1/foundation-records");
    expect(calls[0]?.init?.method).toBe("POST");
  });

  it("reads a record by encoded identifier", async () => {
    const fetchImpl = async () =>
      jsonResponse({
        id: "00000000-0000-0000-0000-000000000001",
        label: "client-check",
        created_at: "2026-11-17T00:00:00Z",
        updated_at: "2026-11-17T00:00:00Z"
      });

    const client = new ApiClient({
      baseUrl: "http://example.test/api/v1",
      fetchImpl: fetchImpl as typeof fetch
    });

    const record = await getFoundationRecord(
      client,
      "00000000-0000-0000-0000-000000000001"
    );

    expect(record.id).toBe("00000000-0000-0000-0000-000000000001");
  });
});
