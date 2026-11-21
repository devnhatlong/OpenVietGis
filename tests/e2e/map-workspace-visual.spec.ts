import { expect, test } from "@playwright/test";

import {
  createMapProject,
  mapSignIn,
  openFixtureMap,
  registerMapReferences,
  saveFixtureMap
} from "./map-fixtures";

test.use({
  viewport: { width: 1440, height: 900 },
  trace: "off",
  screenshot: "off",
  video: "off"
});

test("empty GIS workspace visual baseline", async ({ page }) => {
  await mapSignIn(page);
  const fixture = await createMapProject(
    page,
    Date.now().toString() + "-visual-empty"
  );

  await page.goto(fixture.root + "/map");
  await expect(page.getByTestId("map-workspace")).toBeVisible();
  await expect(page.getByTestId("map-status")).toHaveAttribute(
    "data-state",
    "empty"
  );
  await expect(page.getByTestId("map-workspace-layout")).toHaveAttribute(
    "data-responsive-mode",
    "desktop"
  );

  await expect(page.getByTestId("map-workspace")).toHaveScreenshot(
    "map-workspace-empty.png",
    {
      animations: "disabled",
      mask: [
        page.getByTestId("map-canvas"),
        page.locator(".gis-header h1")
      ]
    }
  );
});

test("populated GIS workspace visual baseline", async ({ page }) => {
  await mapSignIn(page);
  const fixture = await createMapProject(
    page,
    Date.now().toString() + "-visual-data"
  );
  await registerMapReferences(page, fixture, false);
  await saveFixtureMap(page, fixture);

  await openFixtureMap(page, fixture);
  await expect(
    page.getByRole("button", {
      name: "Chọn Points làm lớp hiện hành",
      exact: true
    })
  ).toBeVisible();
  await expect(
    page.getByRole("table", { name: "Bảng thuộc tính theo phiên bản" })
  ).toBeVisible();

  await expect(page.getByTestId("map-workspace")).toHaveScreenshot(
    "map-workspace-populated.png",
    {
      animations: "disabled",
      mask: [
        page.getByTestId("map-canvas"),
        page.locator(".gis-header h1")
      ]
    }
  );
});
