import { describe, expect, it } from "vitest";

import type {
  ProjectMap,
  SpatialLayer
} from "@openvietgis/client-sdk";
import { buildTechnicalDetailsView } from "./technical-details";

const map = {
  map_id: "map-1",
  organization_id: "org-1",
  project_id: "project-1",
  configuration_revision: 7,
  configuration: {
    layers: [],
    basemap: "grid",
    default_viewpoint: null
  }
} as unknown as ProjectMap;

const layer = {
  id: "layer-1",
  source_id: "source-1",
  source: {
    content_revision: "content-7",
    schema_revision: "schema-3",
    source_crs: { authority: "EPSG", code: 4756 },
    stored_crs: { authority: "EPSG", code: 4326 }
  },
  capabilities: [
    {
      name: "render",
      technical_supported: true,
      actor_authorized: true,
      available: true
    },
    {
      name: "style",
      technical_supported: true,
      actor_authorized: false,
      available: true
    },
    {
      name: "edit",
      technical_supported: false,
      actor_authorized: true,
      available: false
    }
  ]
} as unknown as SpatialLayer;

describe("technical details view", () => {
  it("exposes only scoped technical facts needed for support/debugging", () => {
    const view = buildTechnicalDetailsView({
      organizationId: "org-1",
      projectId: "project-1",
      map,
      activeLayer: layer
    });

    expect(view).toMatchObject({
      organizationId: "org-1",
      projectId: "project-1",
      mapId: "map-1",
      configurationRevision: 7,
      activeLayer: {
        layerId: "layer-1",
        sourceId: "source-1",
        contentRevision: "content-7",
        schemaRevision: "schema-3",
        sourceCrs: "EPSG:4756",
        storedCrs: "EPSG:4326"
      }
    });
  });

  it("distinguishes capability support, permission and availability", () => {
    const view = buildTechnicalDetailsView({
      organizationId: "org-1",
      projectId: "project-1",
      map,
      activeLayer: layer
    });

    expect(view.activeLayer?.capabilities).toEqual([
      { name: "render", status: "ready", label: "Sẵn sàng" },
      { name: "style", status: "permission", label: "Không đủ quyền" },
      {
        name: "edit",
        status: "unsupported",
        label: "Không hỗ trợ kỹ thuật"
      }
    ]);
  });

  it("does not invent active-layer metadata when no layer is selected", () => {
    const view = buildTechnicalDetailsView({
      organizationId: "org-1",
      projectId: "project-1",
      map,
      activeLayer: undefined
    });
    expect(view.activeLayer).toBeNull();
  });
});
