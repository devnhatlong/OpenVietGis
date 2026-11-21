import { createHash } from "node:crypto";
import { expect, test } from "@playwright/test";

test("verified package remains readable and draft survives real browser disconnect/reload; sync receipt persists", async ({page,context})=>{
  const expires = new Date(Date.now()+3600_000).toISOString();
  const gpkg = Buffer.from("SQLite format 3\0synthetic checksum fixture; native GPKG tested by Python");
  const snapshot = {
    version:1,package_id:"p1",actor_id:"actor1",organization_id:"org1",project_id:"prj1",
    layer_id:"layer1",layer_name:"Poles",source_id:"src1",content_revision:"revision1",schema_revision:"schema1",
    crs_code:4326,geometry_family:"Point",aoi_bbox:{min_x:105,min_y:20,max_x:106,max_y:21},
    created_at:new Date().toISOString(),expires_at:expires,
    fields:[{field_id:"status",name:"Status",type:"text",nullable:false}],
    features:[{feature_id:"pole1",properties:{status:"baseline"},geometry:{type:"Point",coordinates:[105.5,20.5]}}]
  };
  const projection = Buffer.from(JSON.stringify(snapshot));
  const digest = (buffer:Buffer)=>createHash("sha256").update(buffer).digest("hex");
  const metadata = {id:"p1",name:"Synthetic bundle",profile:"standard_pwa",crs_code:4326,
    feature_count:1,sha256:digest(gpkg),byte_size:gpkg.length,revoked_at:null,expires_at:expires,
    layer_pins:[{layer_id:"layer1",source_id:"src1",content_revision:"revision1",schema_revision:"schema1",snapshot_sha256:digest(projection)}]};
  const submit: unknown[] = [];
  await context.route("**/api/v1/**", async route=>{
    const url = new URL(route.request().url());
    const pathname = url.pathname;
    if(pathname.endsWith("/me")) return route.fulfill({json:{id:"actor1",display_name:"Fixture",status:"active",email_snapshot:null}});
    if(pathname.endsWith("/spatial/layers")) return route.fulfill({json:{items:[]}});
    if(pathname.endsWith("/field/packages")) return route.fulfill({json:{items:[metadata]}});
    if(pathname.endsWith("/download")) return route.fulfill({status:200,body:gpkg,contentType:"application/geopackage+sqlite3"});
    if(pathname.endsWith("/snapshot")) return route.fulfill({status:200,body:projection,contentType:"application/json"});
    if(pathname.endsWith("/auth/csrf")) return route.fulfill({json:{token:"synthetic-token"}});
    if(pathname.endsWith("/sync")) {
      submit.push(route.request().postDataJSON());
      return route.fulfill({status:201,json:{id:"receipt1",status:"applied",applied_changeset_ids:["cs1"],conflicts:[]}});
    }
    return route.abort();
  });
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
  await expect(page.getByTestId("offline-receipt")).toContainText("Đã chấp nhận toàn bộ nhóm");
  expect(submit).toHaveLength(1);
  expect(submit[0]).toMatchObject({operations:[{op_type:"update",feature_id:"pole1",properties:{status:"offline draft"}}]});
  await page.reload();
  await page.getByRole("button",{name:"Mở gói",exact:true}).click();
  await expect(page.getByTestId("offline-receipt")).toContainText("receipt1");
  // A separate browser test fixture used no real authentication or production backend.
  // Service worker caching and IDB/draft/receipt persistence are real.
});
