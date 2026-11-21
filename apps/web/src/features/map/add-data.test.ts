import { describe, expect, it } from "vitest";

import type {
  MapLayerReference,
  SpatialLayer
} from "@openvietgis/client-sdk";
import { buildAddDataCandidates } from "./add-data";

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
