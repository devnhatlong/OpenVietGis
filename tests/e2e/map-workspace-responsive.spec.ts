import { expect, test } from "@playwright/test";

import {
  createMapProject,
  mapSignIn,
  openFixtureMap,
  registerMapReferences,
  saveFixtureMap
} from "./map-fixtures";

test.use({ trace: "off", screenshot: "off", video: "off" });

test("adapts GIS workspace across desktop tablet and mobile reference widths", async ({
  page
}) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1440, height: 900 });
  await mapSignIn(page);

  const fixture = await createMapProject(
    page,
    Date.now().toString() + "-responsive"
  );
  await registerMapReferences(page, fixture, false);
  await saveFixtureMap(page, fixture);
  await openFixtureMap(page, fixture);

  const matrix = [
    { width: 1440, height: 900, mode: "desktop" },
    { width: 1280, height: 900, mode: "desktop" },
    { width: 1024, height: 768, mode: "tablet" },
    { width: 768, height: 720, mode: "tablet" },
    { width: 414, height: 820, mode: "mobile" },
    { width: 375, height: 760, mode: "mobile" }
  ] as const;

  for (const entry of matrix) {
    await page.setViewportSize({
      width: entry.width,
      height: entry.height
    });

    const layout = page.getByTestId("map-workspace-layout");
    await expect(layout).toHaveAttribute("data-responsive-mode", entry.mode);
    await expect(page.getByRole("region", { name: "Khung bản đồ" })).toBeVisible();

    const overflow = await page.evaluate(() => ({
      viewport: window.innerWidth,
      document: document.documentElement.scrollWidth,
      body: document.body.scrollWidth
    }));
    expect(
      Math.max(overflow.document, overflow.body),
      "page-wide overflow at " + entry.width + "px"
    ).toBeLessThanOrEqual(overflow.viewport + 1);
  }

  await page.setViewportSize({ width: 375, height: 760 });
  const controls = page.getByLabel("Điều khiển bố cục");
  await expect(controls).toBeVisible();

  // Mobile is intentionally a basic viewer with optional sheets rather than
  // forced desktop parity.
  const tableToggle = controls.getByRole("button", {
    name: "Bảng thuộc tính",
    exact: true
  });
  await tableToggle.click();
  await expect(tableToggle).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("region", { name: "Khung bản đồ" })).toBeVisible();
});
