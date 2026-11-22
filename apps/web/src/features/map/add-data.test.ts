import { describe, expect, it } from "vitest";

import type {
  MapLayerReference,
  SpatialLayer,
  SpatialLayerList
} from "@openvietgis/client-sdk";
import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { protectedQueryOptions } from "../../app/protected-query";
import { buildAddDataCandidates, currentAddDataCatalog, layerScopeMatches } from "./add-data";

function layer(
  id: string,
  overrides: Partial<SpatialLayer["capabilities"][number]> = {}
): SpatialLayer {
  return {
    id,
    organization_id: "org-1",
    project_id: "project-1",
    source_id: "source-" + id,
    name: "Layer " + id,
    lifecycle: "active",
    source: {
      id: "source-" + id,
      organization_id: "org-1",
      project_id: "project-1",
      name: "Source " + id,
      lifecycle: "active",
      schema: {
        geometry_family: "Point",
        fields: []
      },
      stored_crs: { authority: "EPSG", code: 4326 }
    },
    capabilities: [
      {
        name: "render",
        technical_supported: true,
        available: true,
        actor_authorized: true,
        required_permission: "project.read",
        ...overrides
      }
    ]
  } as unknown as SpatialLayer;
}

function catalog(items: SpatialLayer[]): SpatialLayerList {
  return {
    organization_id: "org-1", project_id: "project-1",
    items, next_after_id: null
  };
}

const reference: MapLayerReference = {
  layer_id: "present",
  visible: true,
  style: { color: "#123456", opacity: 1, width: 2, radius: 5 }
};

describe("add data candidates", () => {
  it("marks existing references without offering a duplicate add", () => {
    const [candidate] = buildAddDataCandidates([layer("present")], [reference]);
    expect(candidate).toMatchObject({
      layerId: "present",
      alreadyOnMap: true,
      addable: false,
      availability: "already-present"
    });
  });

  it("offers an authorized renderable catalog layer", () => {
    const [candidate] = buildAddDataCandidates([layer("new")], [reference]);
    expect(candidate).toMatchObject({
      layerId: "new",
      addable: true,
      availability: "addable",
      geometryFamily: "Point",
      crsLabel: "EPSG:4326"
    });
  });

  it("distinguishes permission denial from unsupported rendering", () => {
    const candidates = buildAddDataCandidates(
      [
        layer("permission", { actor_authorized: false }),
        layer("unsupported", { technical_supported: false })
      ],
      []
    );
    expect(candidates[0]?.availability).toBe("permission");
    expect(candidates[1]?.availability).toBe("unsupported");
  });
});

describe("current scoped catalog and metadata", () => {
  const valid = { data: catalog([layer("a")]), fetchStatus: "idle", isSuccess: true, error: null } as const;

  it("never uses a closed, pending, paused or denied catalog payload", () => {
    expect(currentAddDataCatalog(false, valid, "org-1", "project-1"))
      .toEqual({ status: "loading", page: undefined });
    for (const fetchStatus of ["fetching", "paused"] as const) {
      expect(currentAddDataCatalog(true, { ...valid, fetchStatus }, "org-1", "project-1"))
        .toEqual({ status: "loading", page: undefined });
    }
    expect(currentAddDataCatalog(true, { ...valid, error: new Error("denied") }, "org-1", "project-1"))
      .toEqual({ status: "unavailable", page: undefined });
  });

  it("requires matching outer scope, nested source ownership and exact requested layer ID", () => {
    const a = layer("a");
    expect(layerScopeMatches(a, "org-1", "project-1", "a")).toBe(true);
    expect(layerScopeMatches(a, "org-1", "project-1", "another-layer")).toBe(false);
    for (const invalid of [
      { ...valid.data, organization_id: "wrong" },
      { ...valid.data, project_id: "other" },
      catalog([{ ...a, project_id: "other" }]),
      catalog([{ ...a, source: { ...a.source, organization_id: "wrong" } }]),
      catalog([{ ...a, source: { ...a.source, id: "different" } }])
    ]) {
      expect(currentAddDataCatalog(true, { ...valid, data: invalid }, "org-1", "project-1"))
        .toEqual({ status: "unavailable", page: undefined });
    }
    expect(currentAddDataCatalog(true, valid, "org-1", "project-1"))
      .toEqual({ status: "ready", page: valid.data });
    const empty = catalog([]);
    expect(currentAddDataCatalog(true, { ...valid, data: empty }, "org-1", "project-1"))
      .toEqual({ status: "ready", page: empty });
  });

  it("only fetches on explicit open and withholds cached data during fresh reopen", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    let calls = 0;
    let finish: (page: SpatialLayerList) => void = () => {};
    const options = {
      queryKey: ["account", "org-1", "project-1", "catalog"],
      queryFn: () => { calls++; return new Promise<SpatialLayerList>(resolve => { finish = resolve; }); },
      ...protectedQueryOptions
    };
    const observer = new QueryObserver(client, { ...options, enabled: false });
    const unsubscribe = observer.subscribe(() => {});
    try {
      expect(calls).toBe(0);
      observer.setOptions({ ...options, enabled: true });
      expect(calls).toBe(1);
      expect(currentAddDataCatalog(true, observer.getCurrentResult(), "org-1", "project-1").page).toBeUndefined();
      finish(valid.data);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      expect(currentAddDataCatalog(true, observer.getCurrentResult(), "org-1", "project-1"))
        .toEqual({ status: "ready", page: valid.data });
      observer.setOptions({ ...options, enabled: false });
      expect(currentAddDataCatalog(false, observer.getCurrentResult(), "org-1", "project-1").page).toBeUndefined();
      observer.setOptions({ ...options, enabled: true });
      expect(calls).toBe(2);
      expect(currentAddDataCatalog(true, observer.getCurrentResult(), "org-1", "project-1").page).toBeUndefined();
      finish(catalog([]));
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
      expect(currentAddDataCatalog(true, observer.getCurrentResult(), "org-1", "project-1"))
        .toEqual({ status: "ready", page: catalog([]) });
    } finally {
      unsubscribe();
      client.clear();
    }
  });
});
