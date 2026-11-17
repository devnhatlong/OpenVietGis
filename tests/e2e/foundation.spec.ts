import { expect, test } from "@playwright/test";

test("creates and loads the persisted foundation sample record", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Platform foundation" })).toBeVisible();
  await expect(page.getByTestId("readiness")).toContainText("Foundation ready");

  const label = `e2e-${Date.now()}`;
  await page.getByLabel("Foundation record label").fill(label);
  await page.getByRole("button", { name: "Create record" }).click();

  const record = page.getByTestId("foundation-record");
  await expect(record).toContainText(label);

  const id = await page.getByLabel("Foundation record UUID").inputValue();
  expect(id).toMatch(/^[0-9a-f-]{36}$/);

  await page.reload();
  await page.getByLabel("Foundation record UUID").fill(id);
  await page.getByRole("button", { name: "Load record" }).click();
  await expect(page.getByTestId("foundation-record")).toContainText(label);
});
