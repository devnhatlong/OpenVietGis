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
  await expect(page.getByTestId("confirm-import-btn")).toBeEnabled({
    timeout: 15000
  });
  await page.getByTestId("confirm-import-btn").click();
  await expect(page.getByTestId("import-notice")).toContainText(
    "Nhập dữ liệu thành công",
    { timeout: 15000 }
  );

  // 1. R006 Editing Workbench
  await page.goto(`${base}/editing`);
  await expect(page.getByTestId("editing-workbench")).toBeVisible();
  await page.getByLabel("Hình học 2D GeoJSON").fill('{"type":"Point","coordinates":[105.85,21.02]}');
  await page.getByLabel("Thuộc tính JSON có kiểu").fill('{"name":"Point Two"}');
  await page.getByRole("button", { name: "Đưa vào bản nháp" }).click();
  await page.getByRole("button", { name: "Lưu thay đổi", exact: true }).click();
  await expect(page.getByText(/Đã lưu đợt thay đổi/i)).toBeVisible({ timeout: 10000 });

  // 2. R007 Query Workbench
  await page.goto(`${base}/queries`);
  await expect(page.getByTestId("query-workbench")).toBeVisible();
  await page.getByRole("button", { name: "Chạy truy vấn" }).click();
  await expect(page.getByText(/Kết quả: 2 đối tượng phù hợp/i)).toBeVisible({ timeout: 10000 });

  // 3. R008 Processing Workbench
  await page.goto(`${base}/processing`);
  await expect(page.getByTestId("processing-workbench")).toBeVisible();
  await page.getByRole("button", { name: "Chạy tác vụ" }).click();
  await expect(page.getByText(/hoàn tất \(Thành công, 2 đối tượng\)/i)).toBeVisible({
    timeout: 15000
  });

  // 4. R009 Cartography Workbench
  await page.goto(`${base}/cartography`);
  await expect(page.getByTestId("cartography-workbench")).toBeVisible();
  await page.getByRole("button", { name: "Lưu ký hiệu" }).click();
  await expect(page.getByText(/Đã lưu ký hiệu trung lập/i)).toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "Tạo bố cục in" }).click();
  await expect(page.getByText(/Đã tạo bố cục in A4 ngang/i)).toBeVisible({
    timeout: 10000
  });
  await page.getByRole("button", { name: "PNG 150 DPI" }).first().click();
  await expect(page.getByText(/Đã xuất tệp PNG \(150 DPI/i)).toBeVisible({ timeout: 15000 });

  // 5. R010–R015 Platform Hub (Ops Readiness + COGO)
  await page.goto(`${base}/platform-hub`);
  await expect(page.getByTestId("ops-readiness-panel")).toBeVisible();
  await expect(
    page.getByRole("cell", {
      name: "Vận hành sản xuất & tự triển khai",
      exact: true
    })
  ).toBeVisible({ timeout: 10000 });
  await expect(page.getByText(/Trạng thái phụ thuộc:\s*Sẵn sàng/i)).toBeVisible({
    timeout: 10000
  });
  const opsPanel = page.getByTestId("ops-readiness-panel");
  await expect(opsPanel.getByText(/Hồ sơ phát hành:\s*Chưa nghiệm thu/i)).toBeVisible();
  await expect(opsPanel.getByRole("cell", { name: "Chưa nghiệm thu", exact: true })).toHaveCount(15);

  await page.getByRole("tab", { name: "CAD 2D & COGO", exact: true }).click();
  await page.getByRole("button", { name: "Tính tọa độ điểm cuối" }).click();
  await expect(
    page.getByText(/Tọa độ điểm tính được: \(500100\.0000, 2300000\.0000\)/i)
  ).toBeVisible();
});
