import { chromium, expect, test, type Browser, type Page } from "@playwright/test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { OfflinePackage, SpatialFeaturePage, SpatialLayer, SpatialLayerList } from "../../packages/client-sdk/src";
import { createMapProject, grantMapCollaborator, mapMutation, mapRead, mapSignIn } from "./map-fixtures";

test.use({ viewport:{width:1280,height:900}, trace:"off", screenshot:"off", video:"off" });

type Receipt = { id:string; status:string; applied_changeset_ids:string[]; conflicts:unknown[]; operation_receipts:{client_operation_id:string;local_feature_id:string;core_feature_id:string|null;status:string;changeset_id:string|null}[] };
const map = (p:Page) => p.getByTestId("offline-map");
const draftName = (p:Page) => p.getByLabel("name (text)", {exact:true});
const receipt = (p:Page) => p.getByTestId("offline-receipt");

async function openPack(p:Page, name:string) {
  await p.getByRole("listitem").filter({hasText:name}).getByRole("button",{name:"Mở gói"}).click();
  await expect(map(p)).toBeVisible();
}

async function issue(p:Page, name:string, layerId:string, api:string):Promise<OfflinePackage> {
  await expect(p.getByTestId("offline-shell")).toContainText("đã sẵn sàng");
  await p.getByLabel("Tên gói").fill(name);
  await p.getByLabel("Lớp được cấp quyền").selectOption(layerId);
  for (const [k,v] of Object.entries({min_x:"105",min_y:"20",max_x:"106",max_y:"22"})) await p.getByLabel(k,{exact:true}).fill(v);
  await p.getByLabel(/Tôi xác nhận/).check();
  await p.getByRole("button",{name:"Tạo & tải gói đã xác minh"}).click();
  await expect(p.getByText("Gói đã kiểm tra checksum và lưu trên thiết bị.")).toBeVisible();
  await expect(map(p)).toBeVisible();
  const packs=await mapRead<{items:OfflinePackage[]}>(p,api+"/field/packages");
  return packs.items.find(x=>x.name===name)!;
}

async function edit(p:Page, name:string) {
  await p.getByLabel("Chọn đối tượng").selectOption("field_original");
  await draftName(p).fill(name);
  await p.getByRole("button",{name:"Lưu bản nháp ngoại tuyến"}).click();
  await expect(p.getByText("Hàng đợi bản nháp · 1",{exact:true})).toBeVisible();
}
async function current(p:Page, api:string, layerId:string) {
  const layer=await mapRead<SpatialLayer>(p,api+"/layers/"+layerId);
  const pins=new URLSearchParams({content_revision:layer.source.content_revision,schema_revision:layer.source.schema_revision,include_geometry:"true"});
  return {layer, features:(await mapRead<SpatialFeaturePage>(p,api+"/layers/"+layerId+"/features?"+pins)).items};
}

test("R013 real OIDC + PostGIS: disconnected durable group, lost server acknowledgment, conflict and revocation", async ({baseURL})=>{
  test.setTimeout(240_000);
  const profile=await mkdtemp(join(tmpdir(),"ovg-r013-synthetic-"));
  let context=await chromium.launchPersistentContext(profile,{baseURL,viewport:{width:1280,height:900}});
  let browser:Browser|undefined;
  try {
  const page=context.pages()[0] ?? await context.newPage();
  await mapSignIn(page);
  const fixture=await createMapProject(page,Date.now().toString()+"-offline");
  await page.goto(fixture.root+"/transfers");
  await expect(page.getByTestId("transfers-page")).toBeVisible();
  await page.getByTestId("import-file-input").setInputFiles({
    name:"offline-point.geojson",mimeType:"application/geo+json",
    buffer:Buffer.from(JSON.stringify({type:"FeatureCollection",features:[
      {type:"Feature",id:"field_original",properties:{name:"Original"},geometry:{type:"Point",coordinates:[105.84,21.02]}}
    ]})),
  });
  await expect(page.getByTestId("confirm-import-btn")).toBeEnabled();
  await page.getByTestId("confirm-import-btn").click();
  await expect(page.getByTestId("import-notice")).toContainText("Nhập dữ liệu thành công");
  const layers=await mapRead<SpatialLayerList>(page,fixture.api+"/layers");
  const layer=layers.items[0]!;
  expect(layer.source.feature_count).toBe(1);
  const path="/offline-field/"+fixture.organizationId+"/"+fixture.projectId;
  await page.goto(path);
  let p=page;
  p.on("dialog", d=>void d.accept());
  const initial=await issue(p,"R013 real pack A",layer.id,fixture.api);
  expect(initial.feature_count).toBe(1);
  const pkgApi=fixture.api+"/field/packages/"+initial.id;
  const gpkg=await p.request.get(pkgApi+"/download");
  expect(gpkg.status()).toBe(200);
  expect((await gpkg.body()).subarray(0,16).toString()).toBe("SQLite format 3\x00");
  const projection=await p.request.get(pkgApi+"/snapshot");
  expect(projection.status()).toBe(200);
  expect((await projection.json()).features[0].properties).toEqual({name:"Original"});

  // No mocked API. Chromium enters offline network mode, then both update and capture are persisted.
  await context.setOffline(true);
  await expect(p.getByTestId("offline-connectivity")).toContainText("Mất kết nối");
  await expect(map(p)).toBeVisible();
  await edit(p,"Offline edit");
  await p.getByRole("button",{name:"Điểm mới",exact:true}).click();
  await p.getByLabel("Tọa độ X").fill("105.85");
  await p.getByLabel("Tọa độ Y").fill("21.03");
  await draftName(p).fill("Offline capture");
  await p.getByRole("button",{name:"Xác nhận tọa độ và lưu bản nháp"}).click();
  await expect(p.getByText("Hàng đợi bản nháp · 2",{exact:true})).toBeVisible();
  await expect(p.getByRole("button",{name:"Đồng bộ nhóm bản nháp"})).toBeDisabled();
  // Close the complete Chromium process; the next launch uses only its persisted profile.
  await context.close();
  context=await chromium.launchPersistentContext(profile,{baseURL,offline:true,viewport:{width:1280,height:900}});
  p=context.pages()[0] ?? await context.newPage();
  p.on("dialog", d=>void d.accept());
  await p.goto(path);
  await expect(p.getByTestId("offline-connectivity")).toContainText("Mất kết nối");
  await openPack(p,"R013 real pack A");
  await expect(p.getByText("Hàng đợi bản nháp · 2",{exact:true})).toBeVisible();
  await p.getByLabel("Chọn đối tượng").selectOption("field_original");
  await expect(draftName(p)).toHaveValue("Offline edit");

  await context.setOffline(false);
  await expect(p.getByTestId("offline-connectivity")).toContainText("Trực tuyến");
  await expect(map(p)).toBeVisible();
  expect((await current(p,fixture.api,layer.id)).features).toHaveLength(1);
  // Forward the real HTTP mutation to API/PostGIS, deliberately discard only the ACK.
  let actual:Receipt|undefined;
  let submitted:unknown;
  await context.route("**"+pkgApi+"/sync", async route=>{
    submitted=route.request().postDataJSON();
    const committed=await route.fetch();
    expect(committed.status()).toBe(201);
    actual=await committed.json() as Receipt;
    await route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({detail:"test: response lost after real commit"})});
  });
  await p.getByRole("button",{name:"Đồng bộ nhóm bản nháp"}).click();
  await expect(p.getByRole("button",{name:"Thử lại đúng nhóm đã gửi"})).toBeEnabled();
  await expect.poll(()=>actual?.status).toBe("applied");
  const first=await current(p,fixture.api,layer.id);
  expect(first.features).toHaveLength(2);
  expect(first.features.find(f=>f.feature_id==="field_original")?.attributes.name).toBe("Offline edit");
  const captured=first.features.find(f=>f.attributes.name==="Offline capture");
  expect(captured?.geometry).toMatchObject({type:"Point",coordinates:[105.85,21.03]});
  expect(actual!.operation_receipts).toHaveLength(2);
  const captureReceipt=actual!.operation_receipts.find(r=>r.core_feature_id===captured?.feature_id)!;
  expect(captureReceipt.client_operation_id).toMatch(/^[0-9a-f-]{36}$/);
  expect(captureReceipt.core_feature_id).toMatch(/^field-core-/);
  expect(captureReceipt.local_feature_id).not.toBe(captureReceipt.core_feature_id);
  expect(captureReceipt.changeset_id).toBe(actual!.applied_changeset_ids[0]);
  expect(actual!.operation_receipts.find(r=>r.local_feature_id==="field_original")?.core_feature_id).toBe("field_original");
  await context.unroute("**"+pkgApi+"/sync");
  await p.reload();
  await openPack(p,"R013 real pack A");
  await expect(p.getByRole("button",{name:"Thử lại đúng nhóm đã gửi"})).toBeEnabled();
  const replayRequest=p.waitForRequest(r=>new URL(r.url()).pathname===pkgApi+"/sync");
  await p.getByRole("button",{name:"Thử lại đúng nhóm đã gửi"}).click();
  expect((await replayRequest).postDataJSON()).toEqual(submitted);
  await expect(receipt(p)).toContainText("Đã chấp nhận toàn bộ nhóm");
  await expect(receipt(p)).toContainText(actual!.id);
  await expect(receipt(p)).toContainText(actual!.applied_changeset_ids[0]!);
  await expect(receipt(p)).toContainText(captureReceipt.core_feature_id!);
  await expect(receipt(p)).toContainText(captureReceipt.client_operation_id);
  const afterReplay=await current(p,fixture.api,layer.id);
  expect(afterReplay.layer.source.content_revision).toBe(first.layer.source.content_revision);
  expect(afterReplay.features).toHaveLength(2);

  // A second package has a stale base after independent online Core edit; no blind merge.
  const stale=await issue(p,"R013 real pack B",layer.id,fixture.api);
  await context.setOffline(true);
  await expect(map(p)).toBeVisible();
  await edit(p,"Discarded stale draft");
  await context.setOffline(false);
  await expect(map(p)).toBeVisible();
  const corePath=fixture.api+"/sources/"+layer.source.id+"/changesets";
  const outside=await mapMutation(p,corePath,"POST",{
    base_content_revision:afterReplay.layer.source.content_revision,operation_id:crypto.randomUUID(),
    operations:[{op_type:"update",feature_id:"field_original",properties:{name:"Concurrent Core edit"}}]
  });
  expect(outside.status).toBe(201);
  await p.getByRole("button",{name:"Đồng bộ nhóm bản nháp"}).click();
  await expect(receipt(p)).toContainText("Nhóm không được xuất bản");
  await expect(receipt(p)).toContainText('"conflict"');
  await p.getByLabel("Chọn đối tượng").selectOption("field_original");
  await expect(draftName(p)).toHaveValue("Discarded stale draft");
  await p.getByRole("button",{name:"Đối chiếu dữ liệu hiện tại"}).click();
  await expect(receipt(p)).toContainText("Concurrent Core edit");
  const conflicted=await current(p,fixture.api,layer.id);
  expect(conflicted.features.find(f=>f.feature_id==="field_original")?.attributes.name).toBe("Concurrent Core edit");
  expect(conflicted.features).toHaveLength(2);

  // Revoke the actual downloaded package; client locks it on revalidation and after offline restart.
  expect((await mapMutation(p,fixture.api+"/field/packages/"+stale.id+"/revoke","POST")).status).toBe(200);
  await p.getByRole("button",{name:"Kiểm tra lại quyền và gói"}).click();
  const locked=p.getByRole("listitem").filter({hasText:"R013 real pack B"});
  await expect(locked).toContainText("Bị khóa");
  await expect(locked.getByRole("button",{name:"Mở gói"})).toBeDisabled();
  await expect(map(p)).toHaveCount(0);
  expect((await p.request.get(fixture.api+"/field/packages/"+stale.id+"/snapshot")).status()).toBe(403);
  await context.setOffline(true);
  await p.reload();
  await expect(locked).toContainText("Bị khóa");
  await expect(locked.getByRole("button",{name:"Mở gói"})).toBeDisabled();
  await openPack(p,"R013 real pack A");
  await p.getByRole("button",{name:"Khóa thiết bị ngoại tuyến"}).click();
  await p.reload();
  await expect(p.getByText("Đang khóa dữ liệu",{exact:false})).toBeVisible();
  await expect(map(p)).toHaveCount(0);
  await context.setOffline(false);

  // Transfer only the owner's live auth state (in memory, never to evidence) to
  // ordinary contexts in one Chromium process for the two-user permission test.
  const ownerState=await context.storageState();
  await context.close();
  browser=await chromium.launch();
  context=await browser.newContext({baseURL,storageState:ownerState});
  p=await context.newPage();
  await p.goto(fixture.root+"/map");
  // Distinct actor obtains a writable package only under a real editor grant, then loses it.
  const memberContext=await browser.newContext({baseURL});
  try {
    const member=await memberContext.newPage();
    await mapSignIn(member,true);
    const grant=await grantMapCollaborator(p,member,fixture,"editor");
    const grantsPath="/api/v1/organizations/"+fixture.organizationId+"/grants";
    const membership=(await mapRead<{id:string;subject_id:string}[]>(p,grantsPath)).find(g=>g.id===grant)!.subject_id;
    await member.goto(path);
    const memberPack=await issue(member,"R013 member pack",layer.id,fixture.api);
    await memberContext.setOffline(true);
    await expect(map(member)).toBeVisible();
    await edit(member,"Revoked actor draft");
    // Server-side revocation while the actor has no network.
    const revoked=await mapMutation(p,"/api/v1/organizations/"+fixture.organizationId+"/grants/"+grant+"/revoke","POST");
    expect(revoked.status).toBe(204);
    // Downgrade to viewer rather than removing all project access: ordinary layer reads
    // must still work, but the writable package is no longer authorized.
    const viewer=await mapMutation<{id:string}>(p,grantsPath,"POST",{subject_kind:"membership",subject_id:membership,scope_kind:"project",project_id:fixture.projectId,role:"viewer"});
    expect(viewer.status).toBe(201);
    await memberContext.setOffline(false);
    await expect(member.getByText("Đang khóa dữ liệu",{exact:false})).toBeVisible();
    await expect(map(member)).toHaveCount(0);
    const mapi=fixture.api+"/field/packages/"+memberPack.id;
    expect((await member.request.get(fixture.api+"/layers/"+layer.id)).status()).toBe(200);
    expect((await member.request.get(fixture.api+"/field/packages")).status()).toBe(403);
    expect((await member.request.get(mapi+"/download")).status()).toBe(403);
    expect((await member.request.get(mapi+"/snapshot")).status()).toBe(403);
    const denied=await mapMutation(member,mapi+"/sync","POST",{operation_id:"revoked-actor",operations:[{op_type:"update",feature_id:"field_original",properties:{name:"Revoked actor draft"}}]});
    expect(denied.status).toBe(403);
    await memberContext.setOffline(true);
    await member.reload();
    await expect(member.getByText("Đang khóa dữ liệu",{exact:false})).toBeVisible();
    await expect(map(member)).toHaveCount(0);
    // Reauthorization must not silently unlock the known revoked local pack.
    expect((await mapMutation(p,grantsPath+"/"+viewer.body!.id+"/revoke","POST")).status).toBe(204);
    expect((await mapMutation(p,grantsPath,"POST",{subject_kind:"membership",subject_id:membership,scope_kind:"project",project_id:fixture.projectId,role:"editor"})).status).toBe(201);
    await memberContext.setOffline(false);
    await member.reload();
    const revokedLocal=member.getByRole("listitem").filter({hasText:"R013 member pack"});
    await expect(revokedLocal).toContainText("Bị khóa");
    member.on("dialog",d=>void d.accept());
    await member.getByRole("button",{name:"Mở khóa ngoại tuyến cho tài khoản này"}).click();
    await expect(member.getByText("Thiết bị đã mở khóa ngoại tuyến.")).toBeVisible();
    await memberContext.setOffline(true);
    await member.reload();
    await expect(revokedLocal).toContainText("Bị khóa");
    await expect(revokedLocal.getByRole("button",{name:"Mở gói"})).toBeDisabled();
  } finally {await memberContext.close();}
  expect((await current(p,fixture.api,layer.id)).layer.source.content_revision).toBe(conflicted.layer.source.content_revision);
  } finally {
    await context.close();
    await browser?.close();
    // Profile contains synthetic session cookies and local GIS data; do not retain it.
    await rm(profile,{recursive:true,force:true});
  }
});
