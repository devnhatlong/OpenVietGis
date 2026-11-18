import { expect, test } from "@playwright/test";

test("checks readiness and reloads a persisted real tenant project", async ({ page }) => {
  const readiness = await page.request.get("/api/v1/health/ready", { timeout: 5_000 });
  expect(readiness.status()).toBe(200);
  expect(await readiness.json()).toEqual({ status: "ready", database: "ready" });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to OpenVietGIS" })).toBeVisible();
  await page.getByRole("link", { name: /Continue with OpenVietGIS Development/ }).click();
  await page.locator("#username").fill("owner-a");
  await page.locator("#password").fill("openvietgis-test-owner-a");
  await page.locator("#kc-login").click();
  await expect(page.getByText(/Signed in as/)).toBeVisible();

  const suffix = Date.now();
  const orgName = "Foundation tenant " + suffix;
  await page.getByLabel("Organization name").fill(orgName);
  await page.getByLabel("Organization slug").fill("foundation-" + suffix);
  await page.getByRole("button", { name: "Create organization" }).click();
  await page.getByRole("link", { name: orgName, exact: true }).click();
  await page.getByRole("link", { name: "Projects", exact: true }).click();

  const projectName = "Foundation project " + suffix;
  await page.getByLabel("Project name").fill(projectName);
  await page.getByLabel("Project slug").fill("foundation-project-" + suffix);
  await page.getByRole("button", { name: "Create project" }).click();
  const record = page.locator('li[data-testid^="project-"]').filter({ hasText: projectName });
  await expect(record).toBeVisible();
  const id = await record.getAttribute("data-testid");
  expect(id).toMatch(/^project-[0-9a-f-]{36}$/);
  if (!id) throw new Error("Missing persisted project ID");
  await page.reload();
  await expect(page.getByTestId(id)).toContainText(projectName);
});
