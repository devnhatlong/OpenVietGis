import { expect, test } from "@playwright/test";

import { signInOwner } from "./frontend-auth-helpers";

test.use({ trace: "off", video: "off" });

test("landing visual baseline", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await expect(page).toHaveScreenshot("landing.png", {
    fullPage: true,
    animations: "disabled"
  });
});

test("login visual baseline", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/login");
  await expect(page).toHaveScreenshot("login.png", {
    fullPage: true,
    animations: "disabled"
  });
});

test("authenticated dashboard and account menu visual baselines", async ({
  page
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signInOwner(page);

  await expect(page).toHaveScreenshot("dashboard.png", {
    fullPage: true,
    animations: "disabled"
  });

  await page.getByRole("button", { name: "Mở menu tài khoản" }).click();
  await expect(page).toHaveScreenshot("account-menu.png", {
    fullPage: true,
    animations: "disabled"
  });
});
