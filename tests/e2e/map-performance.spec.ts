import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { cpus, platform, release, totalmem } from "node:os";
import type { MapViewport, SpatialFeatureDetail } from "../../packages/client-sdk/src";
import {
  createMapProject, expectUsableMap, mapSignIn, normalMapViewpoint,
  registerMapReferences, saveFixtureMap
} from "./map-fixtures";

test.use({ viewport: { width: 1280, height: 900 }, trace: "off", screenshot: "off", video: "off" });

function summarize(values: number[]) {
  const sorted = [...values].sort((a, b) => a - b);
  const quantile = (fraction: number) => sorted[Math.ceil(sorted.length * fraction) - 1]!;
  return { count: values.length, p50_ms: quantile(0.5), p95_ms: quantile(0.95), max_ms: sorted.at(-1)! };
}

test("measures 100 actual map-open and select-to-authorized-inspector trials on the 10000-feature Core profile", async ({
  page, browser
}, testInfo) => {
  test.setTimeout(600_000);
  const warmups = 5, trials = 100;
  await mapSignIn(page);
  const fixture = await createMapProject(page, Date.now().toString() + "-benchmark");
  await registerMapReferences(page, fixture);
  expect(fixture.sources.reduce((sum, source) => sum + source.feature_count!, 0)).toBe(10000);
  await saveFixtureMap(page, fixture);
  const externalRequests: string[] = [];
  await page.route(/^https?:\/\/(?!(?:127\.0\.0\.1|localhost)(?::|\/|$))/i, async route => {
    externalRequests.push(new URL(route.request().url()).origin);
    await route.abort();
  });
  const opening: number[] = [];
  const selection: number[] = [];
  let observedViewport: Record<string, string> | null = null;
  let observedCanvas: { width: number; height: number } | null = null;

  for (let index = 0; index < warmups + trials; index++) {
    // Full fresh workspace document/renderer, retaining only normal warmed browser assets and session cookies.
    await page.goto("about:blank");
    const snapshots: Promise<void>[] = [];
    const successfulLayers = new Set<string>();
    const responseListener = (response: import("@playwright/test").Response) => {
      const url = new URL(response.url());
      if (!url.pathname.startsWith(fixture.api + "/layers/") || !url.pathname.endsWith("/viewport")) return;
      snapshots.push((async () => {
        expect(response.status()).toBe(200);
        const body = await response.json() as MapViewport;
        const layer = fixture.layers.find(candidate => candidate.id === body.context.layer_id);
        expect(layer, "viewport must belong to this exact authorized Project fixture").toBeDefined();
        expect(body.context).toMatchObject({
          organization_id: fixture.organizationId, project_id: fixture.projectId,
          source_id: layer!.source_id, content_revision: layer!.source.content_revision,
          schema_revision: layer!.source.schema_revision, geometry_included: true,
          response_crs: { authority: "EPSG", code: 4326, coordinate_order: "xy" }
        });
        expect(body.complete).toBe(true);
        expect(body.limitation).toBeNull();
        expect(body.items.length).toBeGreaterThan(0);
        successfulLayers.add(layer!.id);
        if (!observedViewport) observedViewport = Object.fromEntries(url.searchParams.entries());
      })());
    };
    page.on("response", responseListener);
    try {
      const started = performance.now();
      await page.goto(fixture.root + "/map");
      await expectUsableMap(page);
      await Promise.all(snapshots);
      expect(successfulLayers.size, "usable open must apply all three actual pinned geometry responses").toBe(3);
      const elapsed = performance.now() - started;
      if (index >= warmups) opening.push(elapsed);
      if (!observedCanvas) {
        const box = await page.getByTestId("map-canvas").boundingBox();
        expect(box).not.toBeNull();
        observedCanvas = { width: box!.width, height: box!.height };
      }
    } finally {
      page.off("response", responseListener);
    }
  }

  const points = fixture.layers.find(layer => layer.name === "Points")!;
  await page.getByRole("button", { name: "Make Points active", exact: true }).click();
  const table = page.getByRole("table", { name: "Pinned map attributes" });
  await expect(table.getByRole("button", { name: "point-000001", exact: true })).toBeVisible();
  for (let index = 0; index < warmups + trials; index++) {
    const id = index % 2 === 0 ? "point-000001" : "point-000002";
    const actualDetail = page.waitForResponse(response => {
      const url = new URL(response.url());
      return url.pathname === fixture.api + "/layers/" + points.id + "/features/" + id &&
        response.request().method() === "GET";
    });
    const started = performance.now();
    await table.getByRole("button", { name: id, exact: true }).click();
    const detailResponse = await actualDetail;
    expect(detailResponse.status()).toBe(200);
    const detail = await detailResponse.json() as SpatialFeatureDetail;
    expect(detail.context).toMatchObject({
      organization_id: fixture.organizationId, project_id: fixture.projectId,
      layer_id: points.id, source_id: points.source_id,
      content_revision: points.source.content_revision, schema_revision: points.source.schema_revision
    });
    expect(detail.feature.feature_id).toBe(id);
    await expect(page.getByTestId("map-inspector")).toHaveAttribute("data-feature-id", id);
    await expect(page.getByTestId("feature-select-" + id)).toBeChecked();
    const elapsed = performance.now() - started;
    if (index >= warmups) selection.push(elapsed);
  }

  const sourcePins = fixture.sources.map(source => ({
    source_id: source.id, content_revision: source.content_revision, schema_revision: source.schema_revision,
    manifest_digest: source.provenance.manifest_digest, feature_count: source.feature_count,
    geometry_family: source.schema.geometry_family, crs: source.stored_crs?.code
  }));
  const browserProfile = await page.evaluate(() => ({
    viewport: { width: window.innerWidth, height: window.innerHeight },
    device_pixel_ratio: window.devicePixelRatio, hardware_concurrency: navigator.hardwareConcurrency
  }));
  const report = {
    schema_version: 1, criterion: "R004 SC007", measured_at: new Date().toISOString(),
    exact_sha: execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim(),
    runner: process.env.GITHUB_RUN_ID ? {
      provider: "GitHub Actions", run_id: process.env.GITHUB_RUN_ID,
      runner_name: process.env.RUNNER_NAME, runner_os: process.env.RUNNER_OS
    } : { provider: "local", runner_os: platform() },
    runtime: { node: process.version, browser: browser.version(), platform: platform(), release: release(),
      cpu_model: cpus()[0]?.model, cpu_count: cpus().length, memory_bytes: totalmem() },
    browser_profile: browserProfile, canvas: observedCanvas, designated_viewpoint: normalMapViewpoint,
    observed_viewport_query: observedViewport, source_pins: sourcePins, total_features: 10000,
    external_network: "blocked", external_request_count: externalRequests.length,
    warmup_trials_per_workflow: warmups, measured_trials_per_workflow: trials,
    open: { ...summarize(opening), budget_p95_ms: 3000, raw_ms: opening },
    select: { ...summarize(selection), budget_p95_ms: 1000, raw_ms: selection }
  };
  // Sanitized synthetic measurements only; no cookies, tokens, bodies, identity credentials or traces.
  await mkdir("dist/map-evidence", { recursive: true });
  await writeFile("dist/map-evidence/sc007.json", JSON.stringify(report, null, 2) + "\n");
  await testInfo.attach("R004-SC007-measured-map-workflows", {
    body: JSON.stringify(report), contentType: "application/json"
  });
  expect(externalRequests).toEqual([]);
  expect(opening).toHaveLength(100);
  expect(selection).toHaveLength(100);
  expect(report.open.p95_ms).toBeLessThanOrEqual(3000);
  expect(report.select.p95_ms).toBeLessThanOrEqual(1000);
});
