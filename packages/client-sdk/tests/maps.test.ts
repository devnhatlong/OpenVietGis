import { describe, expect, expectTypeOf, it } from "vitest";
import {
  ApiClient, ApiError, MapApiError, getMap, saveMap, getMapOperation,
  listMapHistory, getMapViewport, getMapDisplayExtent,
  type ProjectMap, type SaveMapInput, type MapSaveReceipt, type MapHistoryPage,
  type MapConfiguration, type MapViewport, type MapDisplayExtent,
  type MapWorkspaceComponents
} from "../src";

const base = "https://example.test/api/v1";
const mapId = "00000000-0000-4000-8000-000000000001";
const operationId = "00000000-0000-4000-8000-000000000002";
const configuration: MapConfiguration = { layers: [], basemap: "grid", default_viewpoint: null };
const current: ProjectMap = {
  map_id: mapId, organization_id: "org", project_id: "project",
  configuration_revision: 0, configuration
};
const intent: SaveMapInput = {
  operation_id: operationId, expected_revision: 0, layers: [], basemap: "grid",
  default_viewpoint: { mode: "preserve" }
};
const receipt: MapSaveReceipt = {
  map_id: mapId, operation_id: operationId, configuration_revision: 1
};

describe("scoped renderer-neutral map SDK", () => {
  it("uses the mandatory generated wire schemas", () => {
    expectTypeOf<ProjectMap>().toEqualTypeOf<MapWorkspaceComponents["schemas"]["ProjectMap"]>();
    expectTypeOf<SaveMapInput>().toEqualTypeOf<MapWorkspaceComponents["schemas"]["SaveMapInput"]>();
    expectTypeOf<MapViewport>().toEqualTypeOf<MapWorkspaceComponents["schemas"]["MapViewport"]>();
    expectTypeOf<MapDisplayExtent>().toEqualTypeOf<MapWorkspaceComponents["schemas"]["MapDisplayExtent"]>();
    expectTypeOf<ReturnType<typeof getMap>>().toEqualTypeOf<Promise<ProjectMap>>();
    expectTypeOf<ReturnType<typeof saveMap>>().toEqualTypeOf<Promise<MapSaveReceipt>>();
  });

  it("encodes each scope/operation component and never writes while reading", async () => {
    const calls: { url: string; method: string; body: unknown; csrf: string | null }[] = [];
    const client = new ApiClient({ baseUrl: base, fetchImpl: (async (input, init) => {
      calls.push({ url: String(input), method: init?.method ?? "GET",
        body: init?.body ?? null, csrf: new Headers(init?.headers).get("x-openvietgis-csrf") });
      return Response.json(current);
    }) as typeof fetch });
    client.setCsrfToken("mutation-only");
    expect(await getMap(client, "o/", "p?")).toEqual(current);
    await getMapOperation(client, "o/", "p?", "op/+?");
    await listMapHistory(client, "o/", "p?");
    await listMapHistory(client, "o/", "p?", { limit: 2, after_revision: 9 });
    expect(calls.map(call => call.url)).toEqual([
      base + "/organizations/o%2F/projects/p%3F/map",
      base + "/organizations/o%2F/projects/p%3F/map/operations/op%2F%2B%3F",
      base + "/organizations/o%2F/projects/p%3F/map/history",
      base + "/organizations/o%2F/projects/p%3F/map/history?limit=2&after_revision=9"
    ]);
    expect(calls.every(call => call.method === "GET" && call.body === null && call.csrf === null)).toBe(true);
  });

  it("sends an exact explicit save intent with PUT and CSRF; returns only the receipt", async () => {
    let seen: RequestInit | undefined;
    let url = "";
    const client = new ApiClient({ baseUrl: base, fetchImpl: (async (input, init) => {
      url = String(input); seen = init; return Response.json(receipt);
    }) as typeof fetch });
    client.setCsrfToken("synthetic-csrf");
    expect(await saveMap(client, "org", "project", intent)).toEqual(receipt);
    expect(url).toBe(base + "/organizations/org/projects/project/map");
    expect(seen?.method).toBe("PUT");
    expect(new Headers(seen?.headers).get("x-openvietgis-csrf")).toBe("synthetic-csrf");
    expect(JSON.parse(String(seen?.body))).toEqual(intent);
    expect(JSON.parse(String(seen?.body))).not.toHaveProperty("camera");
  });

  it("preserves explicit set/clear/preserve viewpoint choices instead of substituting camera", async () => {
    const bodies: SaveMapInput[] = [];
    const client = new ApiClient({ baseUrl: base, fetchImpl: (async (_input, init) => {
      bodies.push(JSON.parse(String(init?.body)) as SaveMapInput); return Response.json(receipt);
    }) as typeof fetch });
    const viewpoint = { longitude: 106, latitude: 20, zoom: 10, bearing: 0, pitch: 0, crs: 4326 } as const;
    for (const default_viewpoint of [
      { mode: "preserve" } as const, { mode: "set", value: viewpoint } as const, { mode: "clear" } as const
    ]) await saveMap(client, "org", "project", { ...intent, default_viewpoint });
    expect(bodies.map(body => body.default_viewpoint)).toEqual([
      { mode: "preserve" }, { mode: "set", value: viewpoint }, { mode: "clear" }
    ]);
  });

  it("reconciles the original operation receipt without assuming it is the current map revision", async () => {
    const client = new ApiClient({ baseUrl: base, fetchImpl: (async input =>
      Response.json(String(input).includes("/operations/") ? receipt : {
        ...current, configuration_revision: 4
      })) as typeof fetch });
    expect((await getMapOperation(client, "org", "project", operationId)).configuration_revision).toBe(1);
    expect((await getMap(client, "org", "project")).configuration_revision).toBe(4);
  });

  it("keeps descending history and immutable before/after evidence unchanged", async () => {
    const page: MapHistoryPage = { items: [{
      map_id: mapId, operation_id: operationId, configuration_revision: 2, prior_revision: 1,
      actor_type: "human", actor_id: "actor", actor_display_snapshot: "Synthetic user",
      created_at: "2026-11-19T10:00:00Z", before_configuration: configuration,
      after_configuration: { ...configuration, layers: [{
        layer_id: "layer", visible: true, style: { color: "#112233", opacity: 0.4, width: 2, radius: 6 }
      }] }
    }], next_after_revision: 2 };
    const client = new ApiClient({ baseUrl: base, fetchImpl: (async () => Response.json(page)) as typeof fetch });
    expect(await listMapHistory(client, "org", "project")).toEqual(page);
  });

  it("sends explicit pins and display bbox, preserving incomplete render/extent states", async () => {
    const urls: string[] = [];
    const viewport = { context: {}, items: [], complete: false, limitation: "byte_limit" };
    const extent = { context: {}, state: "unavailable", bounds: null };
    const client = new ApiClient({ baseUrl: base, fetchImpl: (async input => {
      urls.push(String(input));
      return Response.json(String(input).includes("/viewport?") ? viewport : extent);
    }) as typeof fetch });
    const pins = { content_revision: "content +?", schema_revision: "schema/?" };
    expect(await getMapViewport(client, "o/", "p?", "l/#", {
      ...pins, west: 105, south: 20, east: 106, north: 21, limit: 1000
    })).toEqual(viewport);
    expect(await getMapDisplayExtent(client, "o/", "p?", "l/#", pins)).toEqual(extent);
    expect(urls).toEqual([
      base + "/organizations/o%2F/projects/p%3F/layers/l%2F%23/viewport?content_revision=content+%2B%3F&schema_revision=schema%2F%3F&west=105&south=20&east=106&north=21&limit=1000",
      base + "/organizations/o%2F/projects/p%3F/layers/l%2F%23/display-extent?content_revision=content+%2B%3F&schema_revision=schema%2F%3F"
    ]);
  });

  it.each([
    [409, "STALE_MAP_REVISION"], [409, "OPERATION_INTENT_CONFLICT"], [409, "NO_CHANGES"],
    [409, "STALE_READ_PIN"], [422, "UNSUPPORTED_TRANSFORMATION"], [503, "MAP_READ_UNAVAILABLE"]
  ] as const)("preserves actionable code %s/%s without retry or private detail", async (status, code) => {
    let calls = 0;
    const client = new ApiClient({ baseUrl: base, fetchImpl: (async () => {
      calls++; return Response.json({ code, detail: "private server detail" }, { status });
    }) as typeof fetch });
    const failure = await saveMap(client, "org", "project", intent).catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(MapApiError);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status, code });
    expect(String(failure)).not.toContain("private server detail");
    expect(calls).toBe(1);
  });

  it.each([401, 403, 404, 422])("keeps generic authentication/validation errors generic (%s)", async status => {
    const client = new ApiClient({ baseUrl: base, fetchImpl: (async () =>
      Response.json({ detail: "denied" }, { status })) as typeof fetch });
    const failure = await getMap(client, "org", "project").catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).not.toBeInstanceOf(MapApiError);
    expect(failure).toMatchObject({ status });
  });

  it("does not clamp invalid bounds/limits or silently retry an uncertain save", async () => {
    let calls = 0;
    let url = "";
    const client = new ApiClient({ baseUrl: base, fetchImpl: (async input => {
      calls++; url = String(input); throw new TypeError("transport disconnected");
    }) as typeof fetch });
    await expect(saveMap(client, "org", "project", intent)).rejects.toThrow("transport disconnected");
    expect(calls).toBe(1);
    await expect(getMapViewport(client, "org", "project", "layer", {
      content_revision: "a", schema_revision: "b", west: 190, east: -190, south: 21, north: 20, limit: 1001
    })).rejects.toThrow("transport disconnected");
    expect(url).toContain("west=190&south=21&east=-190&north=20&limit=1001");
    expect(calls).toBe(2);
  });
});
