import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../src/http";
import {
  TransferApiError,
  confirmExport,
  confirmImport,
  downloadDerivedArtifact,
  listTransferJobs,
  previewExport,
  uploadImportAsset
} from "../src/transfers";

describe("transfers client SDK", () => {
  it("uploads multipart asset without forcing application/json header", async () => {
    let seenHeaders: Headers | undefined;
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      seenHeaders = new Headers(init?.headers);
      return new Response(
        JSON.stringify({
          asset: {
            id: "00000000-0000-0000-0000-000000000010",
            organization_id: "org-1",
            project_id: "proj-1",
            filename: "sample.geojson",
            detected_format: "geojson",
            byte_size: 42,
            sha256: "a".repeat(64),
            uploaded_by_display: "Owner",
            created_at: "2026-11-20T00:00:00Z"
          },
          inspection: {
            asset_sha256: "a".repeat(64),
            detected_format: "geojson",
            members: [],
            selected_member: "features",
            requires_member_selection: false,
            requires_crs_resolution: false,
            requires_encoding_resolution: false,
            resolved_source_crs: 4326,
            target_crs: 4326,
            resolved_encoding: "utf-8",
            sample_only: false,
            feature_count: 1,
            geometry_family: "Point",
            dimensions: "XY",
            fields: [],
            findings: [],
            conversions: [],
            confirmable: true,
            inspection_fingerprint: "b".repeat(64)
          }
        }),
        { status: 201, headers: { "content-type": "application/json" } }
      );
    });
    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchImpl: fetchMock });
    client.setCsrfToken("csrf-tok");
    const res = await uploadImportAsset(
      client,
      "org-1",
      "proj-1",
      new Blob(["{}"], { type: "application/geo+json" }),
      "sample.geojson"
    );
    expect(res.asset.detected_format).toBe("geojson");
    expect(seenHeaders?.has("content-type")).toBe(false);
    expect(seenHeaders?.get("x-openvietgis-csrf")).toBe("csrf-tok");
  });

  it("wraps structured transfer errors with code and detail", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify({ code: "STALE_READ_PIN", message: "Revision changed." }),
        { status: 409, headers: { "content-type": "application/json" } }
      );
    });
    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchImpl: fetchMock });
    await expect(
      previewExport(client, "org-1", "proj-1", {
        layer_id: "00000000-0000-0000-0000-000000000020",
        content_revision: "a".repeat(64),
        schema_revision: "b".repeat(64),
        output_format: "geopackage",
        output_crs: 4326
      })
    ).rejects.toMatchObject({
      status: 409,
      code: "STALE_READ_PIN",
      detail: "Revision changed."
    });
  });

  it("confirms import/export, lists jobs, and downloads verified artifact bytes", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/download")) {
        return new Response(new Uint8Array([1, 2, 3]), {
          status: 200,
          headers: {
            "content-type": "application/geopackage+sqlite3",
            "x-content-sha256": "c".repeat(64)
          }
        });
      }
      if (url.includes("/jobs")) {
        return new Response(JSON.stringify({ items: [] }), { status: 200 });
      }
      return new Response(
        JSON.stringify({
          id: "00000000-0000-0000-0000-000000000030",
          organization_id: "org-1",
          project_id: "proj-1",
          operation_id: "00000000-0000-0000-0000-000000000031",
          kind: url.includes("/imports/") ? "import" : "export",
          request_fingerprint: "d".repeat(64),
          status: "succeeded",
          actor_type: "human",
          actor_id: "00000000-0000-0000-0000-000000000001",
          actor_display_snapshot: "Owner",
          attempt_count: 1,
          created_at: "2026-11-20T00:00:00Z",
          updated_at: "2026-11-20T00:00:00Z",
          attempts: []
        }),
        { status: 200 }
      );
    });
    const client = new ApiClient({ baseUrl: "http://127.0.0.1:8000", fetchImpl: fetchMock });
    const imp = await confirmImport(client, "org-1", "proj-1", {
      operation_id: "00000000-0000-0000-0000-000000000031",
      source_asset_id: "00000000-0000-0000-0000-000000000010",
      selected_member: "features",
      source_name: "Imported",
      layer_name: "Imported Layer",
      inspection_fingerprint: "b".repeat(64),
      approved_conversions: []
    });
    expect(imp.status).toBe("succeeded");

    const exp = await confirmExport(client, "org-1", "proj-1", {
      operation_id: "00000000-0000-0000-0000-000000000032",
      layer_id: "00000000-0000-0000-0000-000000000020",
      content_revision: "a".repeat(64),
      schema_revision: "b".repeat(64),
      output_format: "geopackage",
      output_crs: 4326,
      preview_fingerprint: "e".repeat(64),
      approved_disclosures: []
    });
    expect(exp.status).toBe("succeeded");

    const jobs = await listTransferJobs(client, "org-1", "proj-1");
    expect(jobs.items).toEqual([]);

    const dl = await downloadDerivedArtifact(client, "org-1", "proj-1", "art-1");
    expect(dl.sha256).toBe("c".repeat(64));
    expect(new Uint8Array(dl.bytes)).toEqual(new Uint8Array([1, 2, 3]));
    expect(TransferApiError.name).toBe("TransferApiError");
  });
});
