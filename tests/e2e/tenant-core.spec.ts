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