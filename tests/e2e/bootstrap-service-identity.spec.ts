import { expect, test } from "@playwright/test";

test("authenticates through OIDC and initializes the first organization exactly once", async ({
  page
}, testInfo) => {
  test.setTimeout(300_000);
  const authority = process.env.OPENVIETGIS_BOOTSTRAP_SECRET;
  if (!authority) throw new Error("Dedicated test bootstrap authority missing");
  const started = performance.now();
  const status = await page.request.get("/api/v1/bootstrap/status");
  expect(await status.json()).toEqual({ initialized: false });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to OpenVietGIS" })).toBeVisible();
  await page.getByRole("link", { name: /Continue with OpenVietGIS Development/ }).click();
  await page.locator("#username").fill("owner-a");
  await page.locator("#password").fill("openvietgis-test-owner-a");
  await page.locator("#kc-login").click();

  await expect(page.getByRole("heading", { name: "Initialize OpenVietGIS" })).toBeVisible();
  const suffix = Date.now().toString();
  const orgName = "First Organization " + suffix;
  await page.getByLabel("Organization name").fill(orgName);
  await page.getByLabel("Organization slug").fill("first-" + suffix);
  await page.getByLabel("Installation authority").fill("invalid-fixture-authority");
  await page.getByRole("button", { name: "Initialize installation" }).click();
  await expect(page.getByRole("alert")).toHaveText(/Initialization failed/);
  await expect(page.getByLabel("Installation authority")).toHaveValue("");

  await page.getByLabel("Installation authority").fill(authority);
  await page.getByRole("button", { name: "Initialize installation" }).click();
  const createdOrganization = page.getByRole("link", { name: orgName, exact: true });
  await expect(createdOrganization).toBeVisible();
  await createdOrganization.click();
  await expect(page.getByTestId("active-organization")).toContainText("owner");
  const elapsedMs = performance.now() - started;
  await testInfo.attach("sc-011-bootstrap-timing", {
    body: JSON.stringify({ elapsedMs: Math.round(elapsedMs) }),
    contentType: "application/json"
  });
  expect(elapsedMs).toBeLessThan(300_000);

  const csrf = await page.request.get("/api/v1/auth/csrf");
  const denied = await page.request.post("/api/v1/bootstrap/initialize", {
    headers: {
      Authorization: "Bearer " + authority,
      "X-OpenVietGIS-CSRF": (await csrf.json()).token
    },
    data: { organization_name: "Reuse", organization_slug: "reuse-" + suffix }
  });
  expect(denied.status()).toBe(409);
  expect(await (await page.request.get("/api/v1/bootstrap/status")).json()).toEqual({ initialized: true });
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([]);
  expect(await page.evaluate(() => Object.keys(sessionStorage))).toEqual([]);
});
