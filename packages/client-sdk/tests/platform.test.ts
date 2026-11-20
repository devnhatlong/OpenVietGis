import { describe, expect, it, vi } from "vitest";
import {
  ApiClient,
  commitChangeset,
  createProcessingJob,
  executeLayerQuery,
  getOpsReleaseCapabilities,
  printExportDownloadUrl,
  offlinePackageDownloadUrl
} from "../src";

describe("platform R006-R015 SDK helpers", () => {
  it("constructs protected download URLs and invokes R006/R007/R008/R015 endpoints", async () => {
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify({ items: [], total_releases: 15 }), {
        status: 200,
        headers: { "content-type": "application/json" }
      })
    );
    const client = new ApiClient({
      baseUrl: "http://127.0.0.1:8000/api/v1",
      fetchImpl: fetchMock
    });

    await commitChangeset(
      client,
      "org-1",
      "proj-1",
      "src-1",
      { base_content_revision: "a".repeat(64), operation_id: "op-1", summary: "Edit", operations: [] },
      "csrf-1"
    );
    await executeLayerQuery(client, "org-1", "proj-1", "lyr-1", { limit: 10 }, "csrf-1");
    await createProcessingJob(
      client,
      "org-1",
      "proj-1",
      { algorithm_id: "buffer", input_layer_id: "lyr-1", output_name: "Buf", operation_id: "op-2" },
      "csrf-1"
    );
    await getOpsReleaseCapabilities(client);

    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(printExportDownloadUrl("o1", "p1", "e1")).toBe(
      "/api/v1/organizations/o1/projects/p1/cartography/exports/e1/download"
    );
    expect(offlinePackageDownloadUrl("o1", "p1", "pk1")).toBe(
      "/api/v1/organizations/o1/projects/p1/field/packages/pk1/download"
    );
  });
});
