import { expect, test, type Page } from "@playwright/test";

// Synthetic OIDC identities and job-local data only; do not retain secret-bearing surfaces.
test.use({ trace: "off", screenshot: "off", video: "off" });

async function signIn(page: Page) {
  await page.goto("/");
  await page.getByRole("link", { name: /Continue with OpenVietGIS Development/ }).click();
  await page.locator("#username").fill("owner-a");
  await page.locator("#password").fill("openvietgis-test-owner-a");
  await page.locator("#kc-login").click();
  await expect(page.getByText("Owner Alpha", { exact: true })).toBeVisible();
}

async function setup(page: Page, suffix: string) {
  await signIn(page);
  const name = "Spatial team " + suffix;
  await page.getByLabel("Organization name").fill(name);
  await page.getByLabel("Organization slug").fill("spatial-" + suffix);
  await page.getByRole("button", { name: "Create organization" }).click();
  const link = page.getByRole("link", { name, exact: true });
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(/\/organizations\/[0-9a-f-]{36}$/);
  const organization = new URL(page.url()).pathname.split("/").at(-1)!;
  await page.getByRole("link", { name: "Projects", exact: true }).click();
  const projectName = "Spatial project " + suffix;
  await page.getByLabel("Project name").fill(projectName);
  await page.getByLabel("Project slug").fill("spatial-project-" + suffix);
  await page.getByRole("button", { name: "Create project" }).click();
  const row = page.locator('li[data-testid^="project-"]').filter({ hasText: projectName });
  await expect(row).toBeVisible();
  const project = (await row.getAttribute("data-testid"))!.slice("project-".length);
  expect(organization).toMatch(/^[0-9a-f-]{36}$/);
  expect(project).toMatch(/^[0-9a-f-]{36}$/);
  const root = "/organizations/" + organization + "/projects/" + project;
  await page.goto(root + "/spatial");
  await expect(page.getByRole("heading", { name: "Spatial source catalog" })).toBeVisible();
  await page.getByLabel("Logical reference key").fill("reference_points_4326");
  await page.getByLabel("Source name", { exact: true }).fill("Trusted points " + suffix);
  await page.getByRole("button", { name: "Register", exact: true }).click();
  const sourceButton = page.getByRole("list", { name: "Registered sources" }).getByRole("button", { name: "Trusted points " + suffix + " — ready" });
  await expect(sourceButton).toBeVisible();
  await sourceButton.click();
  await page.getByLabel("Layer name", { exact: true }).fill("Reference Layer " + suffix);
  await page.getByRole("button", { name: "Create Layer", exact: true }).click();
  const layerButton = page.getByRole("list", { name: "Registered Layers" }).getByRole("button").filter({ hasText: "Reference Layer " + suffix });
  await expect(layerButton).toBeVisible();
  await layerButton.click();
  await expect(page.getByRole("table", { name: "Pinned feature page" })).toBeVisible();
  return { root, api: "/api/v1" + root, organization, project, suffix };
}

async function mutate(page: Page, path: string, method: "PATCH" | "POST", body: unknown) {
  // Keep the CSRF value entirely inside the browser; it is never a Playwright argument or attachment.
  return page.evaluate(async ({ path, method, body }) => {
    const csrf = await fetch("/api/v1/auth/csrf").then(response => response.json()) as { token: string };
    const response = await fetch(path, { method, headers: { "content-type": "application/json", "x-openvietgis-csrf": csrf.token }, body: JSON.stringify(body) });
    return { status: response.status, body: await response.json() };
  }, { path, method, body });
}

test("registers and inspects stable pinned features, explicit CRS and immutable catalog history", async ({ page }) => {
  test.setTimeout(180_000);
  const data = await setup(page, Date.now().toString());
  const table = page.getByRole("table", { name: "Pinned feature page" });
  await table.getByRole("button", { name: "point-000001", exact: true }).click();
  const selection = page.getByRole("region", { name: "Selected feature detail" });
  await expect(selection.getByRole("heading", { name: "Feature point-000001" })).toBeVisible();
  await expect(selection.getByRole("row").filter({ hasText: "fld_measure" })).toContainText('"0"');
  await expect(selection.getByRole("row").filter({ hasText: "fld_note" })).toContainText('""');
  await page.getByRole("button", { name: "Next features" }).click();
  await expect(table.getByRole("button", { name: "point-000021", exact: true })).toBeVisible();
  await expect(selection.getByRole("heading", { name: "Feature point-000001" })).toBeVisible();
  await page.getByLabel("Response coordinate reference").selectOption("3857");
  await expect(table.getByRole("button", { name: "point-000001", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Feature inspector" })).toContainText("epsg-1024-forward");
  await expect(selection.getByRole("heading", { name: "Feature point-000001" })).toBeVisible();
  await page.getByLabel("Response coordinate reference").selectOption("4326");
  await expect(table).toBeVisible();
  await page.getByText("CRS definitions and approved operations", { exact: true }).click();
  const definitions = page.getByRole("table", { name: "CRS definitions" });
  await expect(definitions).toContainText("EPSG:3405");
  await expect(definitions).toContainText("Definition only");
  await expect(page.getByRole("list", { name: "Approved direct operations" }).getByRole("listitem")).toHaveCount(8);
  const sources = await (await page.request.get(data.api + "/spatial/sources")).json();
  const source = sources.items[0];
  expect(source).toMatchObject({ stored_crs: { code: 4326 }, source_crs: { code: 4326 } });
  const renamed = await mutate(page, data.api + "/spatial/sources/" + source.id, "PATCH", { expected_revision: source.catalog_revision, name: "Concurrent rename " + data.suffix });
  expect(renamed.status).toBe(200);
  await page.getByLabel("New source name", { exact: true }).fill("Stale UI rename");
  await page.getByRole("button", { name: "Rename", exact: true }).click();
  await expect(page.getByRole("alert").filter({ hasText: "The source changed" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Spatial change history" })).toContainText("update_source");
  const sourceAfter = await (await page.request.get(data.api + "/spatial/sources/" + source.id)).json();
  expect(sourceAfter.content_revision).toBe(source.content_revision);
  expect(sourceAfter.schema_revision).toBe(source.schema_revision);
  expect(await page.evaluate(() => ({ local: Object.keys(localStorage), session: Object.keys(sessionStorage) }))).toEqual({ local: [], session: [] });
  const html = await page.locator("main").innerText();
  expect(html).not.toMatch(/postgresql|spatial\.reference_features|ST_TransformPipeline|urn:ogc/);
});

test("blocks stale feature payloads until explicit retry and rejects a mismatched Project URL", async ({ page }) => {
  test.setTimeout(180_000);
  const data = await setup(page, Date.now().toString() + "-isolation");
  const table = page.getByRole("table", { name: "Pinned feature page" });
  await table.getByRole("button", { name: "point-000001", exact: true }).click();
  await expect(page.getByRole("region", { name: "Selected feature detail" })).toBeVisible();
  // The runtime fixture refresh seam is deliberately not public. Inject only the
  // documented HTTP stale response to test the UI; all setup and retry reads are real.
  const featureRoute = "**/api/v1" + data.root + "/layers/*/features?*";
  await page.route(featureRoute, route => route.fulfill({ status: 409, json: { code: "STALE_READ_PIN", detail: "Read pins changed" } }));
  await page.getByRole("button", { name: "Next features" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "The content or schema changed" })).toBeVisible();
  await expect(page.getByRole("table", { name: "Pinned feature page" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Selected feature detail" })).toHaveCount(0);
  await page.unroute(featureRoute);
  await page.getByRole("button", { name: "Reload revisions and restart" }).click();
  await expect(page.getByRole("table", { name: "Pinned feature page" }).getByRole("button", { name: "point-000001", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Selected feature detail" }).getByRole("heading", { name: "Feature point-000001" })).toBeVisible();
  const missing = "00000000-0000-4000-8000-000000000099";
  const badRoot = "/organizations/" + data.organization + "/projects/" + missing;
  for (const path of ["/spatial/sources", "/layers", "/spatial/changes", "/spatial/crs-profiles"]) {
    expect((await page.request.get("/api/v1" + badRoot + path)).status()).toBe(404);
  }
  await page.goto(badRoot + "/spatial");
  await expect(page.getByRole("alert")).toContainText("Unable to load current Project access");
  await expect(page.getByRole("table", { name: "Pinned feature page" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Selected feature detail" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Spatial change history" })).toHaveCount(0);
});

test("removes a warm catalog before a real deleted-Project refetch returns", async ({ page }) => {
  test.setTimeout(180_000);
  const data = await setup(page, Date.now().toString() + "-deleted");
  await page.getByRole("table", { name: "Pinned feature page" }).getByRole("button", { name: "point-000001", exact: true }).click();
  await expect(page.getByRole("region", { name: "Selected feature detail" })).toBeVisible();
  await page.getByRole("link", { name: "← Projects", exact: true }).click();
  expect((await mutate(page, data.api, "PATCH", { status: "deleted" })).status).toBe(200);
  let release = () => {};
  const held = new Promise<void>(resolve => { release = resolve; });
  const matches = (url: URL) => url.pathname === data.api;
  await page.route(matches, async route => { await held; await route.continue(); });
  try {
    const requested = page.waitForRequest(request => matches(new URL(request.url())) && request.method() === "GET");
    const denied = page.waitForResponse(response => matches(new URL(response.url())) && response.request().method() === "GET");
    await page.evaluate(() => window.history.back());
    await requested;
    await expect(page.getByRole("list", { name: "Registered sources" })).toHaveCount(0);
    await expect(page.getByRole("table", { name: "Pinned feature page" })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Spatial change history" })).toHaveCount(0);
    release();
    expect((await denied).status()).toBe(404);
    await expect(page.getByRole("alert")).toContainText("Unable to load current Project access");
    await expect(page.getByRole("list", { name: "Registered sources" })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "Selected feature detail" })).toHaveCount(0);
  } finally {
    release();
    await page.unroute(matches);
  }
});
