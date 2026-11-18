import { describe, expect, expectTypeOf, it } from "vitest";

import {
  ApiClient, ApiError, SpatialApiError, getSpatialFeature, readSpatialFeatures
} from "../src";
import type {
  GetSpatialFeatureOptions, ReadSpatialFeaturesOptions, SpatialFeature,
  SpatialFeatureDetail, SpatialFeaturePage, SpatialFeatureReadContext
} from "../src";

const pins = { content_revision: "a".repeat(64), schema_revision: "b".repeat(64) };
const pinQuery = new URLSearchParams(pins).toString();
const base = "https://test.invalid/api/v1";

describe("pinned spatial Feature SDK", () => {
  it("requires both pins and uses generated page/detail response types", () => {
    expectTypeOf<ReadSpatialFeaturesOptions>().toMatchTypeOf<typeof pins>();
    expectTypeOf<GetSpatialFeatureOptions>().toMatchTypeOf<typeof pins>();
    expectTypeOf<ReturnType<typeof readSpatialFeatures>>().toEqualTypeOf<Promise<SpatialFeaturePage>>();
    expectTypeOf<ReturnType<typeof getSpatialFeature>>().toEqualTypeOf<Promise<SpatialFeatureDetail>>();
    expectTypeOf<SpatialFeaturePage["context"]>().toEqualTypeOf<SpatialFeatureReadContext>();
    expectTypeOf<SpatialFeaturePage["items"][number]>().toEqualTypeOf<SpatialFeature>();
    expectTypeOf<SpatialFeatureDetail["feature"]>().toEqualTypeOf<SpatialFeature>();
  });

  it("encodes each scoped ID and cursor; sends both pins and only explicit options", async () => {
    const calls: { url: string; method: string; body: unknown; csrf: string | null }[] = [];
    const client = new ApiClient({
      baseUrl: base,
      fetchImpl: (async (input, init) => {
        calls.push({
          url: String(input), method: init?.method ?? "GET",
          body: init?.body ?? null, csrf: new Headers(init?.headers).get("x-openvietgis-csrf")
        });
        return Response.json({});
      }) as typeof fetch
    });
    client.setCsrfToken("not-for-reads");
    await readSpatialFeatures(client, "o/", "p?", "l/#", pins);
    await readSpatialFeatures(client, "o/", "p?", "l/#", {
      ...pins, include_geometry: false, limit: 7, after_feature_id: "a +?"
    });
    await readSpatialFeatures(client, "o/", "p?", "l/#", {
      ...pins, include_geometry: true, response_crs: 5899
    });
    await getSpatialFeature(client, "o/", "p?", "l/#", "f/&", pins);
    await getSpatialFeature(client, "o/", "p?", "l/#", "f/&", {
      ...pins, include_geometry: true, response_crs: 4326
    });
    await getSpatialFeature(client, "o/", "p?", "l/#", "f/&", {
      ...pins, include_geometry: false
    });
    const path = base + "/organizations/o%2F/projects/p%3F/layers/l%2F%23/features";
    expect(calls.map(call => call.url)).toEqual([
      path + "?" + pinQuery,
      path + "?" + pinQuery + "&include_geometry=false&limit=7&after_feature_id=a+%2B%3F",
      path + "?" + pinQuery + "&include_geometry=true&response_crs=5899",
      path + "/f%2F%26?" + pinQuery,
      path + "/f%2F%26?" + pinQuery + "&include_geometry=true&response_crs=4326",
      path + "/f%2F%26?" + pinQuery + "&include_geometry=false"
    ]);
    expect(calls.every(call => call.method === "GET" && call.body === null && call.csrf === null))
      .toBe(true);
  });

  it("preserves pinned context, exact typed attributes and the omitted geometry property", async () => {
    const context: SpatialFeatureReadContext = {
      organization_id: "o", project_id: "p", layer_id: "l", source_id: "s",
      ...pins, geometry_included: false, response_crs: null, transformation: null
    };
    const feature: SpatialFeature = {
      feature_id: "a",
      attributes: { fld_integer: 0, fld_decimal: "0.125", fld_text: "", fld_boolean: false, fld_null: null },
      geometry_state: "present"
    };
    const page: SpatialFeaturePage = {
      context, items: [feature], next_after_feature_id: "a"
    };
    const detail: SpatialFeatureDetail = { context, feature };
    const client = new ApiClient({
      baseUrl: base,
      fetchImpl: (async (input) => {
        return Response.json(String(input).includes("/features/a?") ? detail : page);
      }) as typeof fetch
    });
    const actual = await readSpatialFeatures(client, "o", "p", "l", { ...pins, include_geometry: false });
    expect(actual).toEqual(page);
    expect(actual.items[0]).not.toHaveProperty("geometry");
    expect(await getSpatialFeature(client, "o", "p", "l", "a", { ...pins, include_geometry: false }))
      .toEqual(detail);
  });

  it.each([
    [409, "STALE_READ_PIN"], [409, "SOURCE_NOT_READY"], [422, "INVALID_CURSOR"],
    [422, "UNSUPPORTED_CRS"], [422, "UNSUPPORTED_TRANSFORMATION"]
  ] as const)("returns typed spatial error %s %s without fetching fresh pins or retrying", async (status, code) => {
    let count = 0;
    const client = new ApiClient({
      baseUrl: base,
      fetchImpl: (async () => {
        count++;
        return Response.json({ detail: "failure", code }, { status });
      }) as typeof fetch
    });
    for (const invoke of [
      () => readSpatialFeatures(client, "o", "p", "l", pins),
      () => getSpatialFeature(client, "o", "p", "l", "f", pins)
    ]) {
      const failure = await invoke().catch((error: unknown) => error);
      expect(failure).toBeInstanceOf(SpatialApiError);
      expect(failure).toMatchObject({ status, code });
    }
    expect(count).toBe(2);
  });

  it.each([401, 403, 404, 422])("leaves ordinary API errors generic for %s", async status => {
    const client = new ApiClient({
      baseUrl: base,
      fetchImpl: (async () => Response.json({ detail: "failure" }, { status })) as typeof fetch
    });
    const failure = await getSpatialFeature(client, "o", "p", "l", "f", pins)
      .catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).not.toBeInstanceOf(SpatialApiError);
    expect(failure).toMatchObject({ status });
  });
});
