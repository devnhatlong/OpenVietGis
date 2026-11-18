import { ApiError, SpatialApiError } from "@openvietgis/client-sdk";
import { describe, expect, it } from "vitest";

import {
  canReadFeatures, createTraversal, featureDetailKey, featurePageKey,
  featureResponseMatchesScope, formatFeatureValue, isStaleFeaturePin, featureDetailNeedsRevalidation,
  nextFeaturePage, previousFeaturePage, reconcileTraversal,
  restartFeatureTraversal, selectFeature, type FeatureReadScope
} from "./feature-inspector";

const scope: FeatureReadScope = {
  accountId: "actor-a",
  organizationId: "org-a",
  projectId: "project-a",
  layerId: "layer-a",
  sourceId: "source-a",
  contentRevision: "content-a",
  schemaRevision: "schema-a",
  nativeCrs: 5899
};

describe("pinned feature inspector", () => {
  it("isolates every protected scope and pin, and separates pages from exact detail IDs", () => {
    expect(featurePageKey(scope, null)).toEqual([
      "spatial-catalog", "actor-a", "org-a", "project-a", "layers",
      "features", "layer-a", "source-a", "content-a", "schema-a", 5899,
      "native-page", 20, null
    ]);
    for (const key of [
      "accountId", "organizationId", "projectId", "layerId", "sourceId",
      "contentRevision", "schemaRevision"
    ] as const) {
      expect(featurePageKey({ ...scope, [key]: "changed" }, null))
        .not.toEqual(featurePageKey(scope, null));
      expect(featureDetailKey({ ...scope, [key]: "changed" }, "id-1"))
        .not.toEqual(featureDetailKey(scope, "id-1"));
    }
    expect(featurePageKey(scope, "id-1")).not.toEqual(featurePageKey(scope, null));
    expect(featureDetailKey(scope, "id-1")).not.toEqual(featureDetailKey(scope, "id-2"));
    expect(featureDetailKey(scope, "id-1")).not.toEqual(featurePageKey(scope, "id-1"));
    expect(featurePageKey({ ...scope, nativeCrs: 4326 }, null))
      .not.toEqual(featurePageKey(scope, null));
  });

  it("uses server continuations with reversible bounded history, never chooses an implicit ID", () => {
    const first = reconcileTraversal(createTraversal(), scope);
    expect(first).toMatchObject({ cursor: null, history: [], selected: null });
    const selected = selectFeature(first, "feature-000007");
    const second = nextFeaturePage(selected, "feature-000020");
    const third = nextFeaturePage(second, "feature-000040");
    expect(third).toMatchObject({
      cursor: "feature-000040", history: [null, "feature-000020"], selected: "feature-000007"
    });
    expect(previousFeaturePage(third)).toEqual(second);
    expect(previousFeaturePage(second)).toEqual(selected);
    expect(previousFeaturePage(selected)).toEqual(selected);
    expect(nextFeaturePage(third, null)).toEqual(third);
  });

  it.each(["contentRevision", "schemaRevision"] as const)(
    "restarts from page one on stale %s but retains the exact selected ID",
    pin => {
      const existing = nextFeaturePage(
        selectFeature(reconcileTraversal(createTraversal(), scope), "feature-gone"),
        "feature-000020"
      );
      expect(restartFeatureTraversal(existing)).toMatchObject({
        cursor: null, history: [], selected: "feature-gone"
      });
      const refreshed = reconcileTraversal(existing, { ...scope, [pin]: "new-pin" });
      expect(refreshed).toMatchObject({
        cursor: null, history: [], selected: "feature-gone"
      });
      expect(featureDetailKey(refreshed.scope!, refreshed.selected)).toContain("feature-gone");
      expect(reconcileTraversal(existing, scope)).toEqual(existing);
    }
  );

  it("never carries a previous actor, project, Layer or source's selection across scope changes", () => {
    const existing = nextFeaturePage(
      selectFeature(reconcileTraversal(createTraversal(), scope), "private-id"),
      "private-cursor"
    );
    for (const key of ["accountId", "organizationId", "projectId", "layerId", "sourceId"] as const) {
      expect(reconcileTraversal(existing, { ...scope, [key]: "different" })).toMatchObject({
        cursor: null, history: [], selected: null
      });
    }
  });

  it("checks the response scope, both pins and native CRS before exposing a payload", () => {
    const context = {
      organization_id: scope.organizationId,
      project_id: scope.projectId,
      layer_id: scope.layerId,
      source_id: scope.sourceId,
      content_revision: scope.contentRevision,
      schema_revision: scope.schemaRevision,
      geometry_included: true,
      response_crs: {
        authority: "EPSG" as const, code: 5899 as const, coordinate_order: "xy" as const,
        x_axis: "easting" as const, y_axis: "northing" as const, unit: "metre" as const
      },
      transformation: null
    };
    expect(featureResponseMatchesScope(scope, context)).toBe(true);
    for (const field of [
      "organization_id", "project_id", "layer_id", "source_id",
      "content_revision", "schema_revision"
    ] as const) {
      expect(featureResponseMatchesScope(scope, { ...context, [field]: "elsewhere" })).toBe(false);
    }
    expect(featureResponseMatchesScope(scope, { ...context, geometry_included: false })).toBe(false);
    expect(featureResponseMatchesScope(scope, { ...context, response_crs: null })).toBe(false);
    expect(featureResponseMatchesScope(scope, {
      ...context, response_crs: { ...context.response_crs, code: 4326 }
    })).toBe(false);
  });

  it("does not attempt feature reads without current authorized available capability and ready source", () => {
    const capability = {
      name: "feature_read", technical_supported: true, available: true,
      actor_authorized: true, required_permission: "project.read"
    };
    const layer = {
      lifecycle: "active", source: {
        lifecycle: "active", validation_state: "ready", schema: { state: "known" },
        stored_crs: { code: 5899 }
      },
      capabilities: [capability]
    };
    expect(canReadFeatures(layer)).toBe(true);
    expect(canReadFeatures(undefined)).toBe(false);
    expect(canReadFeatures({ ...layer, lifecycle: "retired" })).toBe(false);
    expect(canReadFeatures({ ...layer, capabilities: [] })).toBe(false);
    for (const flag of ["technical_supported", "available", "actor_authorized"] as const) {
      expect(canReadFeatures({
        ...layer, capabilities: [{ ...capability, [flag]: false }]
      })).toBe(false);
    }
    expect(canReadFeatures({
      ...layer, capabilities: [{ ...capability, required_permission: null }]
    })).toBe(false);
    expect(canReadFeatures({
      ...layer, source: { ...layer.source, validation_state: "not_ready" }
    })).toBe(false);
    expect(canReadFeatures({
      ...layer, source: { ...layer.source, lifecycle: "retired" }
    })).toBe(false);
    expect(canReadFeatures({
      ...layer, source: { ...layer.source, stored_crs: null }
    })).toBe(false);
  });

  it("preserves the lexical values and distinguishes NULL, empty string, zero, and booleans", () => {
    expect(formatFeatureValue(null)).toBe("null");
    expect(formatFeatureValue("")).toBe('""');
    expect(formatFeatureValue("0")).toBe('"0"');
    expect(formatFeatureValue(0)).toBe("0");
    expect(formatFeatureValue(false)).toBe("false");
    expect(formatFeatureValue(true)).toBe("true");
    expect(formatFeatureValue(-1000)).toBe("-1000");
    expect(formatFeatureValue("12345678901234567890.123456789012345678"))
      .toBe('"12345678901234567890.123456789012345678"');
    expect(formatFeatureValue("2025-01-01T00:00:00.012345Z"))
      .toBe('"2025-01-01T00:00:00.012345Z"');
  });

  it("latches detail 404 until explicit metadata retry, not merely a background detail refetch", () => {
    expect(featureDetailNeedsRevalidation(false, null)).toBe(false);
    expect(featureDetailNeedsRevalidation(false, new ApiError(404, new Response(null, { status: 404 })))).toBe(true);
    expect(featureDetailNeedsRevalidation(true, null)).toBe(true);
    expect(featureDetailNeedsRevalidation(true, new Error("background refetch failed"))).toBe(true);
    expect(featureDetailNeedsRevalidation(false, new ApiError(403, new Response(null, { status: 403 })))).toBe(false);
    expect(featureDetailNeedsRevalidation(false, new Error("transport error"))).toBe(false);
  });

  it("recognizes a stale read as a typed 409, not ordinary missing or unavailable", () => {
    const response = new Response(null, { status: 409 });
    expect(isStaleFeaturePin(new SpatialApiError(409, response, "STALE_READ_PIN"))).toBe(true);
    expect(isStaleFeaturePin(new SpatialApiError(409, response, "SOURCE_NOT_READY"))).toBe(false);
    expect(isStaleFeaturePin(new ApiError(404, new Response(null, { status: 404 })))).toBe(false);
    expect(isStaleFeaturePin(new Error("stale"))).toBe(false);
  });
});
