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

test("supports keyboard and textual alternatives across the GIS workspace", async ({
  page
}) => {
  test.setTimeout(240_000);
  await page.emulateMedia({ reducedMotion: "reduce" });
  await mapSignIn(page);

  const fixture = await createMapProject(
    page,
    Date.now().toString() + "-accessibility"
  );
  await registerMapReferences(page, fixture, true);
  await saveFixtureMap(page, fixture);
  await openFixtureMap(page, fixture);

  const mapRegion = page.getByRole("region", { name: "Khung bản đồ" });
  await expect(mapRegion).toBeVisible();
  await expect(page.getByTestId("accessible-map-summary")).toContainText(
    "lớp đang hiển thị"
  );

  // MapLibre remains keyboard-enabled and exposes visible zoom/compass controls.
  const mapCanvas = page.locator(".maplibregl-canvas");
  await expect(mapCanvas).toHaveAttribute("tabindex", "0");
  await expect(page.locator(".maplibregl-ctrl-zoom-in")).toBeVisible();
  await expect(page.locator(".maplibregl-ctrl-zoom-out")).toBeVisible();

  const cameraBefore = await page.getByTestId("map-camera-summary").innerText();
  await mapCanvas.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("map-camera-summary")).not.toHaveText(
    cameraBefore
  );

  // Layer ordering has a non-drag keyboard path.
  const lines = fixture.layers.find((layer) => layer.name === "Lines")!;
  const orderBefore = await page
    .locator("[data-testid^=map-layer-]")
    .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-testid")));
  const moveUp = page.getByRole("button", {
    name: "Đưa Lines lên trên",
    exact: true
  });
  await moveUp.focus();
  await page.keyboard.press("Enter");
  const orderAfter = await page
    .locator("[data-testid^=map-layer-]")
    .evaluateAll((nodes) => nodes.map((node) => node.getAttribute("data-testid")));
  expect(orderAfter).not.toEqual(orderBefore);
  expect(orderAfter).toContain("map-layer-" + lines.id);

  // Panel resize is keyboard-operable.
  const separator = page.getByRole("separator", {
    name: "Đổi độ rộng bảng lớp dữ liệu"
  });
  const widthBefore = await separator.getAttribute("aria-valuenow");
  await separator.focus();
  await page.keyboard.press("ArrowRight");
  await expect(separator).not.toHaveAttribute("aria-valuenow", widthBefore ?? "");

  // Table remains the textual feature alternative.
  await expect(
    page.getByRole("table", { name: "Bảng thuộc tính theo phiên bản" })
  ).toBeVisible();

  // Technical drawer closes back to its invoking control.
  const technicalTrigger = page.getByRole("button", {
    name: "Thông tin kỹ thuật",
    exact: true
  });
  await technicalTrigger.focus();
  await page.keyboard.press("Enter");
  const drawer = page.getByRole("dialog", { name: "Thông tin kỹ thuật" });
  await expect(drawer).toBeVisible();
  await drawer
    .getByRole("button", { name: "Đóng thông tin kỹ thuật" })
    .click();
  await expect(technicalTrigger).toBeFocused();

  // Reduced-motion media preference is honored by workspace CSS.
  const motion = await page.getByTestId("map-workspace").evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      animationDuration: style.animationDuration,
      transitionDuration: style.transitionDuration
    };
  });
  const durationMs = (value: string) =>
    value.endsWith("ms")
      ? Number.parseFloat(value)
      : Number.parseFloat(value) * 1000;
  expect(durationMs(motion.animationDuration)).toBeLessThanOrEqual(0.02);
  expect(durationMs(motion.transitionDuration)).toBeLessThanOrEqual(0.02);

  // Focus indication is not color-only/hidden.
  await page
    .getByLabel("Điều khiển bố cục")
    .getByRole("button", { name: "Lớp dữ liệu", exact: true })
    .focus();
  const focusStyle = await page
    .getByLabel("Điều khiển bố cục")
    .getByRole("button", { name: "Lớp dữ liệu", exact: true })
    .evaluate((element) => {
      const style = getComputedStyle(element);
      return {
        outlineStyle: style.outlineStyle,
        outlineWidth: style.outlineWidth
      };
    });
  expect(focusStyle.outlineStyle).not.toBe("none");
  expect(focusStyle.outlineWidth).not.toBe("0px");
});
