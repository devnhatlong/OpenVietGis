import { expect, test, type Page } from "@playwright/test";

// The one-time invitation secret is intentionally transported through the UI once.
// Do not retain DOM snapshots, network bodies, or screenshots from this journey.
test.use({ trace: "off", screenshot: "off", video: "off" });

type UserName = "owner-a" | "member-a" | "member-b";

const users = {
  "owner-a": { password: "openvietgis-test-owner-a", display: "Owner Alpha" },
  "member-a": { password: "openvietgis-test-member-a", display: "Member Alpha" },
  "member-b": { password: "openvietgis-test-member-b", display: "Member Beta" }
} as const;

async function signIn(page: Page, username: UserName) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to OpenVietGIS" })).toBeVisible();
  await page.getByRole("link", { name: /Continue with OpenVietGIS Development/ }).click();
  await page.locator("#username").fill(username);
  await page.locator("#password").fill(users[username].password);
  await page.locator("#kc-login").click();
  await expect(page.getByText(/Signed in as/)).toBeVisible();
  await expect(page.getByText(users[username].display, { exact: true })).toBeVisible();
}

async function currentUserId(page: Page): Promise<string> {
  const response = await page.request.get("/api/v1/me");
  expect(response.status()).toBe(200);
  return (await response.json() as { id: string }).id;
}

async function createOrganization(page: Page, suffix: string): Promise<string> {
  const name = "Invitation team " + suffix;
  await page.getByLabel("Organization name").fill(name);
  await page.getByLabel("Organization slug").fill("invitation-" + suffix);
  await page.getByRole("button", { name: "Create organization" }).click();
  const link = page.getByRole("link", { name, exact: true });
  await expect(link).toBeVisible();
  await link.click();
  await expect(page).toHaveURL(/\/organizations\/[0-9a-f-]{36}$/);
  return new URL(page.url()).pathname.split("/").at(-1) ?? "";
}

async function createProject(page: Page, name: string, slug: string): Promise<string> {
  await page.getByRole("link", { name: "Projects", exact: true }).click();
  await page.getByLabel("Project name").fill(name);
  await page.getByLabel("Project slug").fill(slug);
  await page.getByRole("button", { name: "Create project" }).click();
  const row = page.locator('li[data-testid^="project-"]').filter({ hasText: name });
  await expect(row).toBeVisible();
  return (await row.getAttribute("data-testid"))?.slice("project-".length) ?? "";
}

async function pasteInvitation(page: Page, handoff: string) {
  const field = page.getByLabel("Invitation handoff");
  await expect(field).toBeVisible();
  // Avoid Playwright's fill call logging the secret in a failure diagnostic.
  await field.evaluate((element, value) => {
    if (!(element instanceof HTMLTextAreaElement)) throw new Error("Expected invitation input");
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
    if (!setter) throw new Error("Missing textarea value setter");
    setter.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
  }, handoff);
}

async function submitInvitation(page: Page, handoff: string, status: number) {
  await page.goto("/invitations/accept");
  await expect(page.getByRole("heading", { name: "Accept invitation" })).toBeVisible();
  await pasteInvitation(page, handoff);
  const response = page.waitForResponse((candidate) =>
    new URL(candidate.url()).pathname === "/api/v1/invitations/accept" &&
    candidate.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Accept invitation", exact: true }).click();
  expect((await response).status()).toBe(status);
}

test("recipient-bound invitation grants one project and revocation stops the next protected request", async ({
  page: owner, browser, baseURL
}) => {
  test.setTimeout(120_000);
  const options = { baseURL: baseURL ?? "http://127.0.0.1:5178" };
  const wrongContext = await browser.newContext(options);
  const recipientContext = await browser.newContext(options);
  try {
    const wrong = await wrongContext.newPage();
    const recipient = await recipientContext.newPage();
    await signIn(owner, "owner-a");
    const suffix = Date.now().toString();
    const orgId = await createOrganization(owner, suffix);
    const projectName = "Invited project " + suffix;
    const projectId = await createProject(owner, projectName, "invited-project-" + suffix);
    expect(orgId).toMatch(/^[0-9a-f-]{36}$/);
    expect(projectId).toMatch(/^[0-9a-f-]{36}$/);
    const projectPath = "/api/v1/organizations/" + orgId + "/projects/" + projectId;
    const hiddenProjectName = "Unshared project " + suffix;
    await owner.getByLabel("Project name").fill(hiddenProjectName);
    await owner.getByLabel("Project slug").fill("unshared-project-" + suffix);
    await owner.getByRole("button", { name: "Create project" }).click();
    await expect(owner.getByText(hiddenProjectName, { exact: true })).toBeVisible();

    await owner.getByRole("link", { name: "Organization", exact: false }).click();
    await owner.getByRole("link", { name: "Membership and access" }).click();
    await expect(owner.getByRole("heading", { name: "Invitations", exact: true })).toBeVisible();
    await owner.getByLabel("Recipient email").fill("member-a@example.test");
    await owner.getByLabel("Organization role").selectOption("member");
    await owner.getByLabel("Include resource grant").check();
    const grantFields = owner.getByRole("group", { name: "Invitation resource access" });
    await grantFields.getByLabel("Scope", { exact: true }).selectOption("project");
    await grantFields.getByLabel("Resource", { exact: true }).selectOption({ label: projectName });
    await grantFields.getByLabel("Resource role").selectOption("viewer");
    await owner.getByRole("button", { name: "Issue invitation" }).click();
    const issued = owner.getByRole("region", { name: "Issued invitation" });
    await expect(issued).toBeVisible();
    const handoff = await issued.getByLabel("Invitation handoff").inputValue();
    let parsed: { organization_id: string; secret: string };
    try {
      parsed = JSON.parse(handoff) as typeof parsed;
    } catch {
      throw new Error("Invalid invitation handoff format");
    }
    expect(parsed.organization_id).toBe(orgId);
    expect(parsed.secret.length).toBeGreaterThanOrEqual(32);
    await issued.getByRole("button", { name: "Hide one-time secret" }).click();
    await expect(issued).toHaveCount(0);

    // The wrong verified identity must not consume the invitation or acquire membership.
    await signIn(wrong, "member-b");
    const wrongUserId = await currentUserId(wrong);
    await submitInvitation(wrong, handoff, 400);
    await expect(wrong.getByRole("alert")).toContainText("Unable to accept invitation");
    const wrongOrganizations = await wrong.request.get("/api/v1/me/organizations");
    expect(wrongOrganizations.status()).toBe(200);
    expect((await wrongOrganizations.json() as Array<{ id: string }>).some((org) => org.id === orgId)).toBe(false);

    const unauthorizedDetail = await wrong.goto(projectPath);
    expect(unauthorizedDetail?.status()).toBe(404);
    expect(await unauthorizedDetail?.text()).not.toContain(projectName);

    // The intended identity completes the very same invitation exactly once.
    await signIn(recipient, "member-a");
    const recipientUserId = await currentUserId(recipient);
    await submitInvitation(recipient, handoff, 200);
    await expect(recipient).toHaveURL(new RegExp("/organizations/" + orgId + "$"));
    await expect(recipient.getByTestId("active-organization")).toContainText("member");
    await recipient.getByRole("link", { name: "Projects", exact: true }).click();
    await expect(recipient.getByText(projectName, { exact: true })).toBeVisible();
    await expect(recipient.getByText(hiddenProjectName, { exact: true })).toHaveCount(0);
    expect((await recipient.request.get(projectPath)).status()).toBe(200);

    await submitInvitation(recipient, handoff, 400);
    await expect(recipient.getByRole("alert")).toContainText("Unable to accept invitation");

    // Populate the SPA cache, then leave the project page using in-app navigation.
    // Do not reload the recipient's browser after revocation: stale query data must
    // remain possible so the test can detect the protected-display regression.
    await recipient.getByRole("link", { name: "← Organizations", exact: true }).click();
    await recipient.getByRole("link", { name: "Invitation team " + suffix, exact: true }).click();
    await recipient.getByRole("link", { name: "Projects", exact: true }).click();
    await expect(recipient.getByText(projectName, { exact: true })).toBeVisible();
    await recipient.getByRole("link", { name: "← Organization", exact: true }).click();
    await expect(recipient.getByTestId("active-organization")).toBeVisible();

    // Revoke without logging the recipient out or replacing their browser context.
    await owner.reload();
    const memberList = owner.getByTestId("member-list");
    const memberRow = memberList.locator("li").filter({ hasText: recipientUserId });
    await expect(memberRow).toContainText("active");
    await expect(memberList.locator("li").filter({ hasText: wrongUserId })).toHaveCount(0);
    owner.once("dialog", (dialog) => void dialog.accept());
    await memberRow.getByRole("button", { name: "Revoke", exact: true }).click();
    await expect(memberRow).toContainText("revoked");
    expect((await recipient.request.get(projectPath)).status()).toBe(404);

    // Hold the real refetch in flight once. The previously authorized project
    // must disappear before the denied response arrives, and stay hidden after.
    const projectListPath = "/api/v1/organizations/" + orgId + "/projects";
    let releaseRefetch = () => {};
    const refetchGate = new Promise<void>((resolve) => { releaseRefetch = resolve; });
    const listRoute = (url: URL) => url.pathname === projectListPath;
    await recipient.route(listRoute, async (route) => {
      await refetchGate;
      await route.continue();
    });
    try {
      const requested = recipient.waitForRequest((request) =>
        listRoute(new URL(request.url())) && request.method() === "GET");
      const denied = recipient.waitForResponse((response) =>
        listRoute(new URL(response.url())) && response.request().method() === "GET");
      try {
        // Browser history restores the SPA route and uses the same QueryClient.
        await recipient.evaluate(() => window.history.back());
        await requested;
        await expect(recipient.getByText(projectName, { exact: true })).toHaveCount(0);
      } finally {
        releaseRefetch();
      }
      expect((await denied).status()).toBe(404);
      await expect(recipient.getByRole("alert")).toContainText("Unable to load project access");
      await expect(recipient.getByText(projectName, { exact: true })).toHaveCount(0);
    } finally {
      releaseRefetch();
      await recipient.unroute(listRoute);
    }

    const storage = await recipient.evaluate(() => ({
      local: Object.keys(localStorage),
      session: Object.keys(sessionStorage)
    }));
    expect(storage.local).toEqual([]);
    expect(storage.session).toEqual([]);
  } finally {
    await wrongContext.close();
    await recipientContext.close();
  }
});
