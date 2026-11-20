import { expect, test } from "@playwright/test";
import { createMapProject, mapSignIn } from "./map-fixtures";

test.use({ viewport: { width: 1280, height: 900 }, trace: "off", screenshot: "off", video: "off" });

test("M2+M3 end-to-end: R006 Editing, R007 Query, R008 Processing, R009 Cartography, and R010–R015 Hub", async ({
  page
}) => {
  test.setTimeout(180_000);
  await mapSignIn(page);
  const fixture = await createMapProject(page, Date.now().toString() + "-m2m3");
  const base = fixture.root;

  // Seed an editable point layer via R005 UI import
  await page.goto(`${base}/transfers`);
  await expect(page.getByTestId("transfers-page")).toBeVisible();
  const geojson = JSON.stringify({
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        id: "pt_e2e_1",
        properties: { name: "Point One" },
        geometry: { type: "Point", coordinates: [105.84, 21.02] }
      }
    ]
  });
  await page.getByTestId("import-file-input").setInputFiles({
    name: "e2e-points.geojson",
    mimeType: "application/geo+json",
    buffer: Buffer.from(geojson, "utf-8")
  });
  await expect(page.getByRole("button", { name: /confirm import/i })).toBeEnabled({
    timeout: 15000
  });
  await page.getByRole("button", { name: /confirm import/i }).click();
  await expect(page.getByText(/import succeeded|succeeded/i).first()).toBeVisible({
    timeout: 15000
  });

  // 1. R006 Editing Workbench
  await page.goto(`${base}/editing`);
  await expect(page.getByTestId("editing-workbench")).toBeVisible();
  await page.getByLabel("Typed Properties JSON").fill('{"name":"Point Two"}');
  await page.getByRole("button", { name: "Stage to Draft" }).click();
  await page.getByRole("button", { name: "Commit Changeset" }).click();
  await expect(page.getByText(/Committed changeset/i)).toBeVisible({ timeout: 10000 });

  // 2. R007 Query Workbench
  await page.goto(`${base}/queries`);
  await expect(page.getByTestId("query-workbench")).toBeVisible();
  await page.getByRole("button", { name: "Run Query" }).click();
  await expect(page.getByText(/Results: 2 matched/i)).toBeVisible({ timeout: 10000 });

  // 3. R008 Processing Workbench
  await page.goto(`${base}/processing`);
  await expect(page.getByTestId("processing-workbench")).toBeVisible();
  await page.getByRole("button", { name: "Run Job" }).click();
  await expect(page.getByText(/completed \(succeeded, 2 features\)/i)).toBeVisible({
    timeout: 15000
  });

  // 4. R009 Cartography Workbench
  await page.goto(`${base}/cartography`);
  await expect(page.getByTestId("cartography-workbench")).toBeVisible();
  await page.getByRole("button", { name: "Save Style" }).click();
  await expect(page.getByText(/Saved renderer-neutral style/i)).toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "Create Layout" }).click();
  await expect(page.getByText(/Created A4 landscape print layout/i)).toBeVisible({
    timeout: 10000
  });
  await page.getByRole("button", { name: "PNG 150 DPI" }).first().click();
  await expect(page.getByText(/Generated PNG \(150 DPI/i)).toBeVisible({ timeout: 15000 });

  // 5. R010–R015 Platform Hub (Ops Readiness + COGO)
  await page.goto(`${base}/platform-hub`);
  await expect(page.getByTestId("ops-readiness-panel")).toBeVisible();
  await expect(page.getByRole("cell", { name: "R015", exact: true })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(/Readiness: ready/i)).toBeVisible({ timeout: 10000 });

  await page.getByRole("tab", { name: /R012 CAD & COGO/i }).click();
  await page.getByRole("button", { name: "Compute Traverse" }).click();
  await expect(
    page.getByText(/Computed Endpoint: \(500100\.0000, 2300000\.0000\)/i)
  ).toBeVisible();
});
