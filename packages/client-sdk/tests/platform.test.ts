import { describe, expect, it, vi } from "vitest";
import {
  ApiClient,
  commitChangeset,
  createProcessingJob,
  executeLayerQuery,
  exportExtensionBundle,
  importExtensionBundle,
  transitionExtension,
  updateExtensionRecord,
  type ExtensionPortableBundle,
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


describe("R014 portable extension contracts", () => {
  it("keeps project scope, active manifest and expected record revision in protected requests", async () => {
    const calls: Array<{url: string; body: unknown; method: string | undefined}> = [];
    const fetchMock = vi.fn().mockImplementation(async (url: string, init?: RequestInit) => {
      calls.push({url, body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined, method: init?.method});
      return new Response(JSON.stringify({items:[]}), {status:200, headers:{"content-type":"application/json"}});
    });
    const client = new ApiClient({baseUrl:"http://127.0.0.1:8000/api/v1",fetchImpl:fetchMock});
    await exportExtensionBundle(client,"org","project","example");
    await transitionExtension(client,"org","project","activation","old","new","csrf");
    await updateExtensionRecord(client,"org","project","example","record",{
      expected_manifest_id:"new",expected_revision:2,payload:{name:"test",value:0,flag:false}
    },"csrf");
    const bundle: ExtensionPortableBundle = {bundle:{format:"openvietgis.extension.portable.v1",
      extension_key:"example", origin:{organization_id:"source-org",project_id:"source-project"},
      active_manifest_id:"old",activation_status:"disabled",manifests:[],activation_history:[],records:[]},sha256:"0".repeat(64)};
    await importExtensionBundle(client,"org","project","example",{...bundle,expected_manifest_id:"new"},"csrf");
    expect(calls.map(c=>c.url)).toEqual([
      "http://127.0.0.1:8000/api/v1/organizations/org/projects/project/extensions/example/portable-export",
      "http://127.0.0.1:8000/api/v1/organizations/org/projects/project/extensions/activations/activation/transition",
      "http://127.0.0.1:8000/api/v1/organizations/org/projects/project/extensions/example/records/record",
      "http://127.0.0.1:8000/api/v1/organizations/org/projects/project/extensions/example/portable-import"
    ]);
    expect(calls[1]?.body).toEqual({expected_manifest_id:"old",target_manifest_id:"new"});
    expect(calls[2]?.body).toEqual({expected_manifest_id:"new",expected_revision:2,payload:{name:"test",value:0,flag:false}});
    expect(calls[3]?.body).toEqual({...bundle,expected_manifest_id:"new"});
  });
});
