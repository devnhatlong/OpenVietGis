import { expect, test } from "@playwright/test";

test("verified package remains readable and draft survives real browser disconnect/reload; sync receipt persists", async ({page,context,request})=>{
  // A local static/synthetic server supplies the exact response bytes.
  // No request is forwarded to any live backend, even if SW bypasses routing.
  page.on("dialog",dialog=>void dialog.accept());
  await page.goto("/offline-field/org1/prj1");
  await expect(page.getByTestId("offline-shell")).toHaveText("đã sẵn sàng", {timeout:15_000});
  await expect(page.getByText("Synthetic bundle",{exact:false})).toBeVisible();
  await page.getByRole("checkbox",{name:/Tôi xác nhận/}).check();
  await page.getByRole("button",{name:"Tải & xác minh"}).click();
  await expect(page.getByTestId("offline-map")).toBeVisible();
  await context.setOffline(true);
  await expect(page.getByTestId("offline-connectivity")).toHaveText("Mất kết nối");
  await expect(page.getByTestId("offline-map")).toBeVisible();
  await page.getByLabel("Chọn đối tượng").selectOption("pole1");
  await page.getByLabel("Status (text)").fill("offline draft");
  await page.getByRole("button",{name:"Lưu bản nháp ngoại tuyến"}).click();
  await expect(page.getByText("Hàng đợi bản nháp · 1")).toBeVisible();
  await page.reload();
  await expect(page.getByTestId("offline-connectivity")).toHaveText("Mất kết nối");
  await page.getByRole("button",{name:"Mở gói",exact:true}).click();
  await expect(page.getByText("Hàng đợi bản nháp · 1")).toBeVisible();
  await page.getByLabel("Chọn đối tượng").selectOption("pole1");
  await expect(page.getByLabel("Status (text)")).toHaveValue("offline draft");
  await context.setOffline(false);
  await expect(page.getByTestId("offline-connectivity")).toHaveText("Trực tuyến");
  await expect(page.getByTestId("offline-map")).toBeVisible();
  await page.getByRole("button",{name:"Đồng bộ nhóm bản nháp"}).click();
  await expect(page.getByRole("alert")).toContainText("503");
  await expect(page.getByRole("button",{name:"Thử lại đúng nhóm đã gửi"})).toBeVisible();
  await page.reload();
  await page.getByRole("button",{name:"Mở gói",exact:true}).click();
  await page.getByRole("button",{name:"Thử lại đúng nhóm đã gửi"}).click();
  await expect(page.getByTestId("offline-receipt")).toContainText("Đã chấp nhận toàn bộ nhóm");
  const submit = await (await request.get("/__fixture/submits")).json();
  expect(submit).toHaveLength(2);
  expect(submit[0]).toEqual(submit[1]);
  expect(submit[0]).toMatchObject({operations:[{op_type:"update",feature_id:"pole1",properties:{status:"offline draft"}}]});
  await page.reload();
  await page.getByRole("button",{name:"Mở gói",exact:true}).click();
  await expect(page.getByTestId("offline-receipt")).toContainText("receipt1");
  await page.getByRole("button",{name:"Khóa thiết bị ngoại tuyến"}).click();
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByRole("alert")).toContainText("chưa được mở khóa ngoại tuyến");
  await expect(page.getByTestId("offline-map")).not.toBeVisible();
});
