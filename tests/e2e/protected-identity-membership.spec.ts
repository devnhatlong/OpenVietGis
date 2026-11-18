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

test("unlinking the active identity revalidates the account even when the DELETE succeeds", async ({ page }) => {
  await signInOwner(page);
  const linksPath = "/api/v1/me/identity-links";
  const currentSubject = "synthetic-active-identity";
  const matches = (url: URL) => url.pathname === linksPath;
  let unlinked = false;
  await page.route(matches, async (route) => {
    if (route.request().method() === "DELETE") {
      unlinked = true;
      await route.fulfill({ status: 204 });
      return;
    }
    const remainingLink = { id: "synthetic-other", issuer: "https://identity.example.test", subject: "synthetic-other-subject" };
    await route.fulfill({ json: unlinked ? [remainingLink] : [
      { id: "synthetic-active", issuer: "https://identity.example.test", subject: currentSubject },
      remainingLink
    ] });
  });
  try {
    await page.getByRole("link", { name: "Identity & session" }).click();
    await expect(page.getByText("Owner Alpha", { exact: false })).toBeVisible();
    const activeLink = page.locator("li").filter({ hasText: currentSubject });
    await expect(activeLink).toBeVisible();

    // The server accepted unlink and cascaded the active identity session; the
    // subsequent account read must be denied, not the otherwise successful links read.
    await holdDeniedRead(page, "/api/v1/me", 401,
      () => activeLink.getByRole("button", { name: "Unlink", exact: true }).click(),
      async () => {
        expect(unlinked).toBe(true);
        await expect(page.getByText("Owner Alpha", { exact: false })).toHaveCount(0);
        await expect(page.getByRole("heading", { name: "Identity & session" })).toHaveCount(0);
        await expect(page.getByRole("button", { name: "Sign out" })).toHaveCount(0);
      },
      async () => {
        await expect(page.getByRole("heading", { name: "Sign in to OpenVietGIS" })).toBeVisible();
      });
  } finally {
    await page.unroute(matches);
  }
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
  // A normal server-side lifecycle conflict must keep the safe error notice and
  // administration controls mounted, while child lists may revalidate.
  const memberMutation = (url: URL) =>
    url.pathname.startsWith("/api/v1/organizations/" + organizationId + "/members/");
  await page.route(memberMutation, (route) => route.fulfill({ status: 409, json: { detail: "Conflict" } }));
  try {
    await page.getByTestId("member-list").locator("li").first().getByRole("button", { name: "Suspend" }).click();
    await expect(page.getByRole("alert")).toContainText("Unable to change membership.");
    await expect(page.getByRole("heading", { name: "Invitations", exact: true })).toBeVisible();
    await expect(page.getByTestId("member-list").locator("li").first()).toBeVisible();
  } finally {
    await page.unroute(memberMutation);
  }

  const invitationMutation = (url: URL) => url.pathname === "/api/v1/organizations/" + organizationId + "/invitations";
  await page.route(invitationMutation, (route) => route.fulfill({ status: 422, json: { detail: "Unprocessable" } }));
  try {
    const recipientInput = page.getByLabel("Recipient email");
    await recipientInput.fill("synthetic-recipient@example.test");
    await page.getByRole("button", { name: "Issue invitation" }).click();
    await expect(page.getByText("Unable to issue invitation.", { exact: true })).toBeVisible();
    await expect(recipientInput).toHaveValue("synthetic-recipient@example.test");
    await expect(page.getByRole("region", { name: "Issued invitation" })).toHaveCount(0);
  } finally {
    await page.unroute(invitationMutation);
  }
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
