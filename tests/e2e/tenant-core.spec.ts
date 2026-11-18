import { expect, test } from "@playwright/test";

async function signIn(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sign in to OpenVietGIS" })).toBeVisible();
  await page.getByRole("link", { name: /Continue with OpenVietGIS Development/ }).click();

  await page.locator("#username").fill("owner-a");
  await page.locator("#password").fill("openvietgis-test-owner-a");
  await page.locator("#kc-login").click();

  await expect(page.getByText(/Signed in as/)).toBeVisible();
  await expect(page.getByText("Owner Alpha")).toBeVisible();
}

test("logs in, creates organizations, and switches explicit organization context", async ({
  page
}) => {
  await signIn(page);

  const suffix = Date.now().toString();
  const names = ["Alpha Team", "Beta Team", "Gamma Team"].map(
    (name, index) => name + " " + suffix + "-" + index
  );

  for (const [index, name] of names.entries()) {
    await page.getByLabel("Organization name").fill(name);
    await page
      .getByLabel("Organization slug")
      .fill("e2e-" + suffix + "-" + index.toString());
    await page.getByRole("button", { name: "Create organization" }).click();
    await expect(page.getByRole("link", { name })).toBeVisible();
  }

  const first = page.getByRole("link", { name: names[0] ?? "" });
  await first.click();
  await expect(page).toHaveURL(/\/organizations\/[0-9a-f-]{36}$/);
  await expect(page.getByTestId("active-organization")).toContainText("owner");

  await page.getByRole("link", { name: names[1] ?? "" }).click();
  await expect(page.getByRole("heading", { name: names[1] ?? "" })).toBeVisible();

  const workspaceA1 = "Workspace A1 " + suffix;
  const workspaceA2 = "Workspace A2 " + suffix;
  await page.getByRole("link", { name: "Workspaces" }).click();
  for (const [index, workspaceName] of [workspaceA1, workspaceA2].entries()) {
    await page.getByLabel("Workspace name").fill(workspaceName);
    await page
      .getByLabel("Workspace slug")
      .fill("workspace-" + suffix + "-" + index.toString());
    await page.getByRole("button", { name: "Create workspace" }).click();
    await expect(page.getByText(workspaceName, { exact: true })).toBeVisible();
  }

  await page.getByRole("link", { name: "Projects" }).click();
  const projectName = "Project P1 " + suffix;
  await page.getByLabel("Project name").fill(projectName);
  await page.getByLabel("Project slug").fill("project-" + suffix);
  await page.getByLabel("Project workspace").selectOption({ label: workspaceA1 });
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByText(projectName, { exact: true })).toBeVisible();

  const projectWorkspace = page.getByLabel("Workspace for " + projectName);
  const a2Value = await projectWorkspace
    .getByRole("option", { name: workspaceA2 })
    .getAttribute("value");
  expect(a2Value).toBeTruthy();
  const projectRow = page
    .locator('li[data-testid^="project-"]')
    .filter({ hasText: projectName });

  await projectWorkspace.selectOption({ label: workspaceA2 });
  await page.getByRole("button", { name: "Move " + projectName }).click();
  await expect(projectRow).toContainText("workspace " + a2Value);

  await page.getByRole("button", { name: "Ungroup " + projectName }).click();
  await expect(projectRow).toContainText("workspace none");

  await page.getByRole("button", { name: "Archive " + projectName }).click();
  await expect(projectRow).toContainText("archived");

  const storage = await page.evaluate(() => ({
    local: Object.keys(localStorage),
    session: Object.keys(sessionStorage)
  }));
  expect(storage.local).toEqual([]);
  expect(storage.session).toEqual([]);
});

test("direct tenant URL substitution cannot resolve another organization's project", async ({ page }) => {
  test.setTimeout(90_000);
  await signIn(page);
  const suffix = Date.now().toString();
  const orgNames = ["Isolation A " + suffix, "Isolation B " + suffix];
  const organizations: string[] = [];

  for (const [index, name] of orgNames.entries()) {
    await page.goto("/");
    await page.getByLabel("Organization name").fill(name);
    await page.getByLabel("Organization slug").fill("isolation-" + suffix + "-" + index);
    await page.getByRole("button", { name: "Create organization" }).click();
    const link = page.getByRole("link", { name, exact: true });
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL(/\/organizations\/[0-9a-f-]{36}$/);
    organizations.push(new URL(page.url()).pathname.split("/").at(-1) ?? "");
  }

  const [orgA, orgB] = organizations;
  expect(orgA).toMatch(/^[0-9a-f-]{36}$/);
  expect(orgB).toMatch(/^[0-9a-f-]{36}$/);
  expect(orgA).not.toBe(orgB);
  // Both Organizations legitimately belong to the same authenticated Owner.
  // Replacing only the explicit tenant ID must still not resolve the other tenant's Project.
  const projectAName = "Private isolation project A " + suffix;
  const projectBName = "Private isolation project B " + suffix;
  const projectAIds: string[] = [];
  for (const [orgId, name] of [[orgA, projectAName], [orgB, projectBName]] as const) {
    await page.goto("/organizations/" + orgId + "/projects");
    await page.getByLabel("Project name").fill(name);
    await page.getByLabel("Project slug").fill("isolation-project-" + suffix);
    await page.getByRole("button", { name: "Create project" }).click();
    const row = page.locator('li[data-testid^="project-"]').filter({ hasText: name });
    await expect(row).toBeVisible();
    const id = (await row.getAttribute("data-testid"))?.slice("project-".length) ?? "";
    expect(id).toMatch(/^[0-9a-f-]{36}$/);
    projectAIds.push(id);
  }

  const [projectAId, projectBId] = projectAIds;
  await page.goto("/organizations/" + orgB + "/projects");
  await expect(page.getByText(projectBName, { exact: true })).toBeVisible();
  await expect(page.getByText(projectAName, { exact: true })).toHaveCount(0);

  // Direct browser navigation, not a UI-only disabled button or hidden route.
  const detailA = await page.goto("/api/v1/organizations/" + orgA + "/projects/" + projectAId);
  expect(detailA?.status()).toBe(200);
  expect((await detailA?.json() as { id: string; organization_id: string })).toMatchObject({
    id: projectAId, organization_id: orgA
  });

  const mismatched = await page.goto("/api/v1/organizations/" + orgB + "/projects/" + projectAId);
  expect(mismatched?.status()).toBe(404);
  const mismatchBody = await mismatched?.text() ?? "";
  expect(mismatchBody).not.toContain(projectAName);
  expect(mismatchBody).not.toContain("isolation-project-" + suffix);

  const reverseMismatch = await page.goto("/api/v1/organizations/" + orgA + "/projects/" + projectBId);
  expect(reverseMismatch?.status()).toBe(404);
  expect(await reverseMismatch?.text()).not.toContain(projectBName);

  const detailB = await page.goto("/api/v1/organizations/" + orgB + "/projects/" + projectBId);
  expect(detailB?.status()).toBe(200);
  expect((await detailB?.json() as { id: string; organization_id: string })).toMatchObject({
    id: projectBId, organization_id: orgB
  });
});
