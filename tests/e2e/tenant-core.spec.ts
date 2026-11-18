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
}, testInfo) => {
  test.setTimeout(120_000);
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

  // Start in one Organization and perform three real switches without signing out.
  const organizationIds = new Map<string, string>();
  for (const name of names) {
    const href = await page.getByRole("link", { name, exact: true }).getAttribute("href");
    const id = href?.split("/").at(-1) ?? "";
    expect(id).toMatch(/^[0-9a-f-]{36}$/);
    organizationIds.set(name, id);
  }
  expect(new Set(organizationIds.values()).size).toBe(3);
  await page.getByRole("link", { name: names[0] ?? "", exact: true }).click();
  await expect(page.getByTestId("active-organization")).toContainText(organizationIds.get(names[0] ?? "") ?? "");

  const timings: Array<{ switchNumber: number; elapsedMs: number }> = [];
  for (const [index, name] of [names[2], names[0], names[1]].entries()) {
    if (!name) throw new Error("Missing switch target");
    const id = organizationIds.get(name);
    if (!id) throw new Error("Missing organization ID");
    const started = performance.now();
    await page.getByRole("link", { name, exact: true }).click();
    await expect(page).toHaveURL(new RegExp("/organizations/" + id + "$"));
    await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
    const context = page.getByTestId("active-organization");
    await expect(context).toContainText(id);
    await expect(context).toContainText("owner");

    // A heading alone does not establish resource access. Wait for the scoped
    // API response and a rendered project list at the explicit target route.
    const projectList = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/v1/organizations/" + id + "/projects" &&
      response.request().method() === "GET"
    );
    await page.getByRole("link", { name: "Projects", exact: true }).click();
    expect((await projectList).status()).toBe(200);
    await expect(page).toHaveURL(new RegExp("/organizations/" + id + "/projects$"));
    await expect(page.getByTestId("project-list")).toBeVisible();
    const elapsedMs = performance.now() - started;
    timings.push({ switchNumber: index + 1, elapsedMs: Math.round(elapsedMs) });
    await testInfo.attach("sc-001-switch-" + (index + 1), {
      body: JSON.stringify(timings.at(-1)),
      contentType: "application/json"
    });
    expect(elapsedMs).toBeLessThan(10_000);
    await page.getByRole("link", { name: "← Organization", exact: true }).click();
    await expect(page.getByRole("heading", { name, exact: true })).toBeVisible();
  }
  const organizationId = organizationIds.get(names[1] ?? "");
  if (!organizationId) throw new Error("Missing organization for workspace journey");

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
  if (!a2Value) throw new Error("Missing destination workspace ID");
  const projectRow = page
    .locator('li[data-testid^="project-"]')
    .filter({ hasText: projectName });

  const projectId = (await projectRow.getAttribute("data-testid"))?.slice("project-".length) ?? "";
  expect(projectId).toMatch(/^[0-9a-f-]{36}$/);
  async function assertOwnership(workspaceId: string | null, status: "active" | "archived") {
    const response = await page.request.get("/api/v1/organizations/" + organizationId + "/projects/" + projectId);
    expect(response.status()).toBe(200);
    expect(await response.json()).toMatchObject({
      id: projectId, organization_id: organizationId, workspace_id: workspaceId, status
    });
  }
  const originalWorkspaceId = await projectWorkspace.inputValue();
  expect(originalWorkspaceId).toMatch(/^[0-9a-f-]{36}$/);
  expect(originalWorkspaceId).not.toBe(a2Value);
  await assertOwnership(originalWorkspaceId, "active");

  await projectWorkspace.selectOption({ label: workspaceA2 });
  await page.getByRole("button", { name: "Move " + projectName }).click();
  await expect(projectRow).toContainText("workspace " + a2Value);
  await assertOwnership(a2Value, "active");

  await page.getByRole("button", { name: "Ungroup " + projectName }).click();
  await expect(projectRow).toContainText("workspace none");
  await assertOwnership(null, "active");

  await page.getByRole("button", { name: "Archive " + projectName }).click();
  await expect(projectRow).toContainText("archived");
  await assertOwnership(null, "archived");

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
