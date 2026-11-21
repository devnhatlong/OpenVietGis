import { expect, test } from "@playwright/test";
import type { MapHistoryPage, MapSaveReceipt, SaveMapInput } from "../../packages/client-sdk/src";
import {
  createMapProject, currentMap, grantMapCollaborator, mapMutation, mapRead, mapSignIn,
  openFixtureMap, registerMapReferences, saveFixtureMap
} from "./map-fixtures";

// Real local OIDC/API/PostGIS/renderer boundaries. No secret-bearing tracing surfaces.
test.use({ viewport: { width: 1280, height: 900 }, trace: "off", screenshot: "off", video: "off" });

test("opens a real empty grid and arranges, renders, selects and saves catalog Layers without changing data", async ({ page }) => {
  test.setTimeout(240_000);
  await mapSignIn(page);
  const fixture = await createMapProject(page, Date.now().toString() + "-workspace");
  const externalRequests: string[] = [];
  await page.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (["http:", "https:"].includes(url.protocol) && !["127.0.0.1", "localhost"].includes(url.hostname)) {
      externalRequests.push(url.origin); await route.abort(); return;
    }
    await route.continue();
  });
  await page.goto(fixture.root + "/map");
  await expect(page.getByTestId("map-workspace")).toBeVisible();
  await expect(page.getByTestId("map-status")).toHaveText("empty");
  expect((await currentMap(page, fixture)).configuration_revision).toBe(0);

  await registerMapReferences(page, fixture);
  await page.reload();
  for (const layer of fixture.layers) {
    await page.getByTestId("add-map-layer").selectOption(layer.id);
    await page.getByRole("button", { name: "+ Thêm lớp có sẵn", exact: true }).click();
    await expect(page.getByTestId("map-layer-" + layer.id)).toBeVisible();
  }
  const fittedLayers = new Set<string>();
  const fittedViewport = async (response: import("@playwright/test").Response) => {
    const url = new URL(response.url());
    if (!url.pathname.endsWith("/viewport") || response.request().method() !== "GET" || response.status() !== 200) return;
    const body = await response.json() as {
      complete: boolean;
      context: { layer_id: string };
    };
    if (!body.complete && fixture.layers.some(layer => layer.id === body.context.layer_id)) {
      fittedLayers.add(body.context.layer_id);
    }
  };
  page.on("response", fittedViewport);
  try {
    await page.getByRole("button", { name: "Thu phóng toàn bộ lớp hiển thị", exact: true }).click();
    await expect.poll(() => fittedLayers.size, { timeout: 30_000 }).toBe(fixture.layers.length);
  } finally {
    page.off("response", fittedViewport);
  }
  await expect(page.getByTestId("map-engine-ready")).toHaveAttribute("data-ready", "true");
  await expect(page.getByTestId("map-status")).toHaveText("partial", {
    timeout: 15_000
  });

  const points = fixture.layers[0]!;
  await page.getByRole("button", { name: "Chọn Points làm lớp hiện hành", exact: true }).click();
  const table = page.getByRole("table", { name: "Bảng thuộc tính theo phiên bản" });
  await expect(table.getByRole("button", { name: "point-000001", exact: true })).toBeVisible();
  await table.getByRole("button", { name: "point-000001", exact: true }).click();
  await expect(page.getByTestId("map-inspector")).toHaveAttribute("data-feature-id", "point-000001");
  await expect(page.getByTestId("feature-select-point-000001")).toBeChecked();

  // Fit the real selected geometry, then independently pick its rendered center.
  const extentDetail = page.waitForResponse(response =>
    new URL(response.url()).pathname.endsWith("/features/point-000001") && response.request().method() === "GET"
  );
  await page.getByRole("button", { name: "Thu phóng vùng chọn", exact: true }).click();
  expect((await extentDetail).status()).toBe(200);
  await expect(page.getByTestId("map-engine-ready")).toHaveAttribute("data-ready", "true");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("map-inspector")).not.toHaveAttribute("data-feature-id", "point-000001");
  const canvas = page.getByTestId("map-canvas");
  await canvas.click();
  await expect(page.getByTestId("map-inspector")).toHaveAttribute("data-feature-id", "point-000001");
  await expect(page.getByTestId("feature-select-point-000001")).toBeChecked();
  await page.getByTestId("feature-select-point-000002").check();
  await expect(page.getByTestId("map-inspector")).toHaveAttribute("data-feature-id", "point-000002");
  await expect(page.getByRole("region", { name: "Bảng thuộc tính bản đồ" })).toContainText("2 đang chọn");
  await page.getByRole("region", { name: "Bảng thuộc tính bản đồ" })
    .getByRole("button", { name: "Trang sau", exact: true }).click();
  await expect(table.getByRole("button", { name: "point-000101", exact: true })).toBeVisible();
  await expect(page.getByTestId("map-inspector")).toHaveAttribute("data-feature-id", "point-000002");
  await expect(page.getByRole("region", { name: "Bảng thuộc tính bản đồ" })).toContainText("2 đang chọn");

  await page.getByRole("button", { name: "Bỏ chọn", exact: true }).click();
  await page.getByRole("checkbox", { name: "Hiển thị Points", exact: true }).uncheck();
  await canvas.click();
  await expect(page.getByTestId("map-inspector")).not.toHaveAttribute("data-feature-id", "point-000001");
  await page.getByRole("button", { name: "Đưa Polygons lên trên", exact: true }).click();
  await page.getByTestId("map-layer-" + points.id).getByText("Tùy chỉnh hiển thị", { exact: true }).click();
  await page.getByTestId("color-" + points.id).fill("#224466");
  const shared = page.getByRole("region", { name: "Cấu hình bản đồ dùng chung" });
  const savedResponse = page.waitForResponse(response =>
    new URL(response.url()).pathname === fixture.api + "/map" && response.request().method() === "PUT"
  );
  await shared.getByRole("button", { name: "Lưu bản đồ", exact: true }).click();
  expect((await savedResponse).status()).toBe(200);
  await expect(page.getByTestId("map-save-status")).toContainText("committed");
  const persisted = await currentMap(page, fixture);
  expect(persisted.configuration_revision).toBe(1);
  // Incidental fit/zoom/selection never designates a shared startup camera.
  expect(persisted.configuration.default_viewpoint).toBeNull();
  expect(persisted.configuration.layers.find(layer => layer.layer_id === points.id)).toMatchObject({
    visible: false, style: { color: "#224466" }
  });
  await page.reload();
  await expect(page.getByRole("checkbox", { name: "Hiển thị Points", exact: true })).not.toBeChecked();
  await expect(page.getByTestId("color-" + points.id)).toHaveValue("#224466");
  for (const original of fixture.sources) {
    const after = await mapRead<typeof original>(page, fixture.api + "/spatial/sources/" + original.id);
    expect(after).toEqual(original);
  }
  expect(externalRequests).toEqual([]);
});

test("preserves the designated camera and reconciles a genuinely committed lost acknowledgement after a later save", async ({ page }) => {
  test.setTimeout(240_000);
  await mapSignIn(page);
  const fixture = await createMapProject(page, Date.now().toString() + "-recovery");
  await registerMapReferences(page, fixture, false);
  await saveFixtureMap(page, fixture);
  await openFixtureMap(page, fixture);
  const original = await currentMap(page, fixture);
  const shared = page.getByRole("region", { name: "Cấu hình bản đồ dùng chung" });
  await page.getByRole("button", { name: "Phóng to (+)", exact: true }).click();
  await page.getByRole("checkbox", { name: "Hiển thị Points", exact: true }).uncheck();
  let capturedIntent: SaveMapInput | null = null;
  const saveUrl = (url: URL) => url.pathname === fixture.api + "/map";
  await page.route(saveUrl, async route => {
    if (route.request().method() !== "PUT") { await route.continue(); return; }
    capturedIntent = route.request().postDataJSON() as SaveMapInput;
    const committed = await route.fetch();
    expect(committed.status()).toBe(200);
    await route.abort("connectionreset");
  });
  await shared.getByRole("button", { name: "Lưu bản đồ", exact: true }).click();
  await expect(page.getByTestId("map-save-status")).toContainText("unresolved");
  await page.unroute(saveUrl);
  const committed = await currentMap(page, fixture);
  expect(committed.configuration_revision).toBe(2);
  expect(committed.configuration.default_viewpoint).toEqual(original.configuration.default_viewpoint);
  if (!capturedIntent) throw new Error("No actual save operation observed");
  const originalOperation = capturedIntent as SaveMapInput;
  const later = await mapMutation<MapSaveReceipt>(page, fixture.api + "/map", "PUT", {
    ...originalOperation, operation_id: crypto.randomUUID(), expected_revision: 2,
    layers: committed.configuration.layers.map(layer => ({ ...layer, visible: true }))
  });
  expect(later.status).toBe(200);
  expect(later.body!.configuration_revision).toBe(3);
  await shared.getByRole("button", { name: "Đối chiếu bản lưu", exact: true }).click();
  await expect(page.getByTestId("map-save-status")).toContainText("committed");
  const receipt = await mapRead<MapSaveReceipt>(page, fixture.api + "/map/operations/" + originalOperation.operation_id);
  expect(receipt.configuration_revision).toBe(2);
  expect((await currentMap(page, fixture)).configuration_revision).toBe(3);
  const replay = await mapMutation<MapSaveReceipt>(page, fixture.api + "/map", "PUT", originalOperation);
  expect(replay.status).toBe(200);
  expect(replay.body).toEqual(receipt);
  const history = await mapRead<MapHistoryPage>(page, fixture.api + "/map/history");
  expect(history.items.map(item => item.configuration_revision)).toEqual([3, 2, 1]);
  await page.reload();
  await expect(page.getByRole("checkbox", { name: "Hiển thị Points", exact: true })).toBeChecked();
  await expect(page.getByTestId("map-save-status")).toContainText("phiên bản 3");
});

test("two real actors receive CAS conflicts and revoked access clears a warm rendered selection", async ({ page: owner, browser, baseURL }) => {
  test.setTimeout(300_000);
  await mapSignIn(owner);
  const fixture = await createMapProject(owner, Date.now().toString() + "-actors");
  await registerMapReferences(owner, fixture, false);
  await saveFixtureMap(owner, fixture);
  const context = await browser.newContext({ baseURL, viewport: { width: 1280, height: 900 } });
  try {
    const editor = await context.newPage();
    await mapSignIn(editor, true);
    const grantId = await grantMapCollaborator(owner, editor, fixture, "editor");
    await openFixtureMap(owner, fixture);
    await openFixtureMap(editor, fixture);
    await owner.getByRole("checkbox", { name: "Hiển thị Points", exact: true }).uncheck();
    await owner.getByRole("region", { name: "Cấu hình bản đồ dùng chung" })
      .getByRole("button", { name: "Lưu bản đồ", exact: true }).click();
    await expect(owner.getByTestId("map-save-status")).toContainText("phiên bản 2");
    const shared = editor.getByRole("region", { name: "Cấu hình bản đồ dùng chung" });
    await shared.getByRole("button", { name: "Xóa góc nhìn mặc định", exact: true }).click();
    await shared.getByRole("button", { name: "Lưu bản đồ", exact: true }).click();
    await expect(editor.getByTestId("map-save-status")).toContainText("conflict");
    expect((await currentMap(owner, fixture)).configuration_revision).toBe(2);
    await shared.getByRole("button", { name: "Tải lại bản đồ chung", exact: true }).click();
    await expect(editor.getByTestId("map-save-status")).toContainText("phiên bản 2");
    await editor.getByRole("checkbox", { name: "Hiển thị Points", exact: true }).check();
    await editor.getByTestId("feature-select-point-000001").check();
    await expect(editor.getByTestId("map-inspector")).toHaveAttribute("data-feature-id", "point-000001");
    const revoked = await mapMutation(owner,
      "/api/v1/organizations/" + fixture.organizationId + "/grants/" + grantId + "/revoke", "POST");
    expect(revoked.status).toBe(204);
    const denied = editor.waitForResponse(response =>
      new URL(response.url()).pathname === fixture.api + "/map" && response.request().method() === "GET"
    );
    await editor.getByRole("button", { name: "Kiểm tra lại quyền truy cập", exact: true }).click();
    expect((await denied).status()).toBe(403);
    await expect(editor.getByRole("table", { name: "Bảng thuộc tính theo phiên bản" })).toHaveCount(0);
    await expect(editor.getByTestId("map-inspector")).toHaveCount(0);
    const forbidden = await mapMutation(editor, fixture.api + "/map", "PUT", {
      operation_id: crypto.randomUUID(), expected_revision: 2, layers: [], basemap: "grid",
      default_viewpoint: { mode: "preserve" }
    });
    expect(forbidden.status).toBe(403);
    expect((await currentMap(owner, fixture)).configuration_revision).toBe(2);
  } finally {
    await context.close();
  }
});

test("a real viewer can preview locally while direct shared mutation stays denied", async ({ page: owner, browser, baseURL }) => {
  test.setTimeout(240_000);
  await mapSignIn(owner);
  const fixture = await createMapProject(owner, Date.now().toString() + "-viewer");
  await registerMapReferences(owner, fixture, false);
  await saveFixtureMap(owner, fixture);
  const context = await browser.newContext({ baseURL, viewport: { width: 1280, height: 900 } });
  try {
    const viewer = await context.newPage();
    await mapSignIn(viewer, true);
    await grantMapCollaborator(owner, viewer, fixture, "viewer");
    await openFixtureMap(viewer, fixture);
    await viewer.getByRole("checkbox", { name: "Hiển thị Points", exact: true }).uncheck();
    await expect(viewer.getByRole("checkbox", { name: "Hiển thị Points", exact: true })).not.toBeChecked();
    await expect(viewer.getByRole("region", { name: "Cấu hình bản đồ dùng chung" })
      .getByRole("button", { name: "Lưu bản đồ", exact: true })).toBeDisabled();
    const attempted = await mapMutation(viewer, fixture.api + "/map", "PUT", {
      operation_id: crypto.randomUUID(), expected_revision: 1, layers: [], basemap: "grid",
      default_viewpoint: { mode: "clear" }
    });
    expect(attempted.status).toBe(403);
    expect((await currentMap(owner, fixture)).configuration_revision).toBe(1);
    await viewer.reload();
    await expect(viewer.getByRole("checkbox", { name: "Hiển thị Points", exact: true })).toBeChecked();
  } finally {
    await context.close();
  }
});
