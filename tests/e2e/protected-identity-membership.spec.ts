import { expect, test, type Page } from "@playwright/test";

// Authentication and invitations must not be retained in browser artifacts.
test.use({ trace: "off", screenshot: "off", video: "off" });

async function signInOwner(page: Page) {
  await page.goto("/");
  await page.getByRole("link", { name: /Continue with OpenVietGIS Development/ }).click();
  await page.locator("#username").fill("owner-a");
  await page.locator("#password").fill("openvietgis-test-owner-a");
  await page.locator("#kc-login").click();
  await expect(page.getByText("Owner Alpha", { exact: true })).toBeVisible();
}

async function holdDeniedRead(
  page: Page,
  path: string,
  status: number,
  navigate: () => Promise<void>,
  checkHidden: () => Promise<void>,
  checkDenied: () => Promise<void>
) {
  const matches = (url: URL) => url.pathname === path;
  let release = () => {};
  const held = new Promise<void>((resolve) => { release = resolve; });
  await page.route(matches, async (route) => {
    await held;
    await route.fulfill({ status, json: { detail: "Denied" } });
  });
  try {
    const requested = page.waitForRequest((request) => matches(new URL(request.url())) && request.method() === "GET");
    await navigate();
    await requested;
    await checkHidden();
    release();
    await checkDenied();
    await checkHidden();
  } finally {
    release();
    await page.unroute(matches);
  }
}

test("identity links never render a private cached payload during or after a denied refetch", async ({ page }) => {
  await signInOwner(page);
  const path = "/api/v1/me/identity-links";
  const sentinel = "synthetic-private-subject";
  const matches = (url: URL) => url.pathname === path;
  await page.route(matches, (route) => route.fulfill({
    json: [
      { id: "synthetic-one", issuer: "https://identity.example.test", subject: sentinel },
      { id: "synthetic-two", issuer: "https://identity.example.test", subject: "synthetic-other-subject" }
    ]
  }));
  const identityLink = page.getByRole("link", { name: "Identity & session" });
  await identityLink.click();
  await expect(page.getByText(sentinel, { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: "Unlink", exact: true })).toHaveCount(2);
  await page.getByRole("link", { name: "← Organizations" }).click();
  await expect(identityLink).toBeVisible();
  await page.unroute(matches);

  // In-app navigation preserves a warm cache. Only the delayed network response differs.
  await holdDeniedRead(page, path, 403, () => identityLink.click(), async () => {
    await expect(page.getByText(sentinel, { exact: false })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Unlink", exact: true })).toHaveCount(0);
    await expect(page.getByRole("link", { name: /^Link / })).toHaveCount(0);
  }, async () => {
    await expect(page.getByRole("alert")).toContainText("Unable to load linked identities.");
  });
});

test("membership administration is unmounted while prior permissions are revalidated", async ({ page }) => {
  await signInOwner(page);
  const suffix = Date.now().toString();
  const organizationName = "Membership freshness " + suffix;
  await page.getByLabel("Organization name").fill(organizationName);
  await page.getByLabel("Organization slug").fill("membership-freshness-" + suffix);
  await page.getByRole("button", { name: "Create organization" }).click();
  await page.getByRole("link", { name: organizationName, exact: true }).click();
  const organizationId = new URL(page.url()).pathname.split("/").at(-1);
  expect(organizationId).toMatch(/^[0-9a-f-]{36}$/);

  const membershipLink = page.getByRole("link", { name: "Membership and access" });
  await membershipLink.click();
  await expect(page.getByTestId("member-list").locator("li").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "Resource grants" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Invitations", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "← Organization", exact: true }).click();
  await expect(membershipLink).toBeVisible();

  await holdDeniedRead(page, "/api/v1/organizations/" + organizationId + "/effective-permissions", 403,
    () => membershipLink.click(),
    async () => {
      await expect(page.getByTestId("member-list")).toHaveCount(0);
      await expect(page.getByTestId("resource-grant-list")).toHaveCount(0);
      await expect(page.getByRole("heading", { name: "Invitations", exact: true })).toHaveCount(0);
      await expect(page.getByRole("region", { name: "Issued invitation" })).toHaveCount(0);
    },
    async () => {
      await expect(page.getByRole("alert")).toContainText("Unable to load organization access.");
    });
});

test("invitation acceptance is hidden during account refetch and preserves login return-to on denial", async ({ page }) => {
  await signInOwner(page);
  const acceptLink = page.getByRole("link", { name: "Accept invitation", exact: true });
  await acceptLink.click();
  await expect(page.getByLabel("Invitation handoff")).toBeVisible();
  await page.getByRole("link", { name: "← Organizations", exact: true }).click();
  await expect(acceptLink).toBeVisible();

  await holdDeniedRead(page, "/api/v1/me", 401, () => acceptLink.click(), async () => {
    await expect(page.getByLabel("Invitation handoff")).toHaveCount(0);
  }, async () => {
    await expect(page.getByRole("heading", { name: "Sign in to OpenVietGIS" })).toBeVisible();
    const login = page.getByRole("link", { name: /Continue with OpenVietGIS Development/ });
    const href = await login.getAttribute("href");
    expect(new URL(href ?? "", page.url()).searchParams.get("return_to")).toBe("/invitations/accept");
  });
});
