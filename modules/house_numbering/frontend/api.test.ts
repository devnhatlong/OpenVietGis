import { ApiClient } from "@openvietgis/client-sdk";
import { describe, expect, it, vi } from "vitest";
import {
  createHouseNumberingRoute,
  houseNumberingDocumentDownloadUrl,
  importHouseNumberingEvidence,
  inspectHouseNumberingLocation,
  listHouseNumberingRoutes
} from "./api";

describe("house-numbering module API", () => {
  it("keeps all calls project scoped", async () => {
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "content-type": "application/json" }
      })
    );
    const client = new ApiClient({
      baseUrl: "http://127.0.0.1:8000/api/v1",
      fetchImpl: fetchMock
    });

    await listHouseNumberingRoutes(client, "org 1", "proj/1");
    await createHouseNumberingRoute(client, "org 1", "proj/1", {
      name: "Đường A",
      route_type: "street",
      source_id: "src-1",
      feature_id: "road-1",
      direction_state: "forward",
      source_label: "map",
      status: "confirmed"
    });
    await inspectHouseNumberingLocation(client, "org 1", "proj/1", {
      x: 100,
      y: 200,
      crs_code: 3857,
      route_id: "route-1",
      rule_id: "rule-1"
    });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[0]?.[0]).toContain(
      "/organizations/org%201/projects/proj%2F1/modules/house-numbering/routes"
    );
    expect(fetchMock.mock.calls[1]?.[1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[2]?.[1]?.body).toContain('"crs_code":3857');
  });

  it("uses multipart import and scoped artifact URLs", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ batch: {}, replayed: false, rejections: [] }), {
        status: 201,
        headers: { "content-type": "application/json" }
      })
    );
    const client = new ApiClient({
      baseUrl: "http://127.0.0.1:8000/api/v1",
      fetchImpl: fetchMock
    });
    const file = new File(["raw_number\n2\n"], "evidence.csv", { type: "text/csv" });

    await importHouseNumberingEvidence(client, "o", "p", {
      file,
      source_format: "csv",
      origin: "certificate",
      mapping: { raw_number: "raw_number" },
      default_source_reference: "CERT-1"
    });

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
    expect(houseNumberingDocumentDownloadUrl("o", "p", "d")).toBe(
      "/api/v1/organizations/o/projects/p/modules/house-numbering/documents/d/download"
    );
  });
});
