import { expect, test } from "@playwright/test";
import type { SpatialFeaturePage, SpatialLayer, SpatialLayerList } from "../../packages/client-sdk/src";
import { createMapProject, mapMutation, mapRead, mapSignIn, type MapFixture } from "./map-fixtures";

test.use({ viewport: { width: 1280, height: 900 }, trace: "off", screenshot: "off", video: "off" });

async function importFixture(page: Parameters<typeof mapSignIn>[0], fixture: MapFixture, name: string, geometry: unknown, properties: Record<string, unknown> = {name:"Original"}) {
  await page.goto(fixture.root + "/transfers");
  await expect(page.getByTestId("transfers-page")).toBeVisible();
  await page.getByTestId("import-file-input").setInputFiles({
    name: name + ".geojson", mimeType: "application/geo+json",
    buffer: Buffer.from(JSON.stringify({ type: "FeatureCollection", features: [
      { type: "Feature", id: "original", properties, geometry }
    ] }))
  });
  await expect(page.getByTestId("confirm-import-btn")).toBeEnabled({timeout: 15000});
  await page.getByTestId("confirm-import-btn").click();
  await expect(page.getByTestId("import-notice")).toContainText("Nhập dữ liệu thành công", {timeout: 15000});
  const layers = await mapRead<SpatialLayerList>(page, fixture.api + "/layers");
  expect(layers.items).toHaveLength(1);
  return layers.items[0]!;
}

async function readCurrent(page: Parameters<typeof mapSignIn>[0], fixture: MapFixture, layerId: string) {
  const layer = await mapRead<SpatialLayer>(page, fixture.api + "/layers/" + layerId);
  const query = new URLSearchParams({
    content_revision: layer.source.content_revision, schema_revision: layer.source.schema_revision, include_geometry: "true"
  });
  return mapRead<SpatialFeaturePage>(page, fixture.api + "/layers/" + layerId + "/features?" + query);
}

async function commit(page: Parameters<typeof mapSignIn>[0], summary: string) {
  await page.getByLabel("Mô tả đợt chỉnh sửa").fill(summary);
  await page.getByRole("button", { name: "Đưa vào bản nháp", exact: true }).click();
  await expect(page.getByTestId("draft-revision")).toContainText("1 thao tác");
  await page.getByRole("button", {name: "Lưu thay đổi", exact: true}).click();
  await expect(page.getByText(/Đã lưu đợt thay đổi/i)).toBeVisible({timeout: 10000});
}

test("native graphical point drawing, visual snap, revision-pinned update/delete/revert and stale draft", async ({page}) => {
  test.setTimeout(120_000);
  await page.route(/^https?:\/\/(?!(?:127\.0\.0\.1|localhost)(?::|\/|$))/i, route => route.abort());
  await mapSignIn(page);
  const fixture = await createMapProject(page, Date.now() + "-draw-point");
  const layer = await importFixture(page, fixture, "draw-point", {type: "Point", coordinates: [105.84, 21.02]}, {name:"Original", measure:1.5});
  await page.goto(fixture.root + "/editing");
  const canvas = page.getByTestId("native-edit-canvas");
  await expect(canvas).toBeVisible();
  const mark = canvas.locator('[data-feature-id="original"]');
  await expect(mark).toBeVisible();
  await mark.scrollIntoViewIfNeeded();
  const box = await mark.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width / 2 + 3, box!.y + box!.height / 2);
  await expect(page.getByTestId("snap-highlight")).toBeVisible();
  await expect(page.getByTestId("snap-status")).toContainText("original");
  await page.mouse.click(box!.x + box!.width / 2 + 3, box!.y + box!.height / 2);
  await expect(page.getByTestId("draft-vertex-0")).toBeVisible();
  await page.getByRole("button", { name: "Dùng hình học đã vẽ" }).click();
  const geometry = JSON.parse(await page.getByLabel("Hình học 2D GeoJSON").inputValue()) as {coordinates: number[]};
  expect(geometry.coordinates).toEqual([105.84, 21.02]);
  await page.getByLabel("Mã đối tượng").fill("snap_create");
  await page.getByLabel("Thuộc tính JSON có kiểu").fill('{"name":"Snapped point","measure":"2.00"}');
  await page.getByRole("button", {name: "Đưa vào bản nháp"}).click();
  await expect(page.getByLabel("Nguồn dữ liệu có thể biên tập")).toBeDisabled();
  await page.getByRole("button", {name: "Hoàn tác (1)", exact: true}).click();
  await page.getByRole("button", {name: "Làm lại (1)", exact: true}).click();
  await page.getByLabel("Mô tả đợt chỉnh sửa").fill("Browser snapped point");
  await page.getByRole("button", {name: "Lưu thay đổi", exact: true}).click();
  await expect(page.getByText(/Đã lưu đợt thay đổi/i)).toBeVisible();
  const afterCreate = await readCurrent(page, fixture, layer.id);
  expect(afterCreate.items.find(f => f.feature_id === "snap_create")?.geometry?.coordinates).toEqual([105.84, 21.02]);
  expect(afterCreate.items.find(f => f.feature_id === "snap_create")?.attributes.measure).toBe("2");

  await page.getByRole("combobox", {name:"Thao tác", exact:true}).selectOption("update");
  await page.getByRole("combobox", {name:"Chọn đối tượng hiện có", exact:true}).selectOption("snap_create");
  await page.getByLabel("Bám điểm và đoạn").uncheck();
  await page.getByTestId("draft-vertex-0").click();
  const area = await canvas.boundingBox();
  await page.mouse.click(area!.x + area!.width * .65, area!.y + area!.height * .55);
  await page.getByRole("button", {name: "Hoàn tác đỉnh"}).click();
  await page.getByRole("button", {name: "Làm lại đỉnh"}).click();
  await page.getByRole("button", {name: "Dùng hình học đã vẽ"}).click();
  const moved = JSON.parse(await page.getByLabel("Hình học 2D GeoJSON").inputValue()) as {coordinates: number[]};
  expect(moved.coordinates).not.toEqual([105.84,21.02]);
  await commit(page, "Browser moved point");
  const afterMove = await readCurrent(page, fixture, layer.id);
  expect(afterMove.items.find(f => f.feature_id === "snap_create")?.geometry?.coordinates).toEqual(moved.coordinates);
  expect(afterMove.items.find(f => f.feature_id === "original")?.geometry?.coordinates).toEqual([105.84,21.02]);

  await page.getByRole("combobox", {name:"Thao tác", exact:true}).selectOption("delete");
  await page.getByRole("combobox", {name:"Chọn đối tượng hiện có", exact:true}).selectOption("snap_create");
  await commit(page, "Browser deleted point");
  expect((await readCurrent(page, fixture, layer.id)).items.map(f => f.feature_id)).toEqual(["original"]);
  await page.getByRole("row").filter({hasText:"Browser deleted point"}).getByRole("button", {name:"Hoàn nguyên"}).click();
  await expect(page.getByText(/Đã hoàn nguyên bộ thay đổi/i)).toBeVisible();
  expect((await readCurrent(page, fixture, layer.id)).items.map(f => f.feature_id)).toEqual(["original", "snap_create"]);

  // Independent mutation after local staging must produce a conflict, not an
  // automatic rebase onto the current source revision.
  await page.getByRole("combobox", {name:"Thao tác", exact:true}).selectOption("update");
  await page.getByRole("combobox", {name:"Chọn đối tượng hiện có", exact:true}).selectOption("snap_create");
  await page.getByLabel("Thuộc tính JSON có kiểu").fill('{"name":"Stale draft","measure":"2"}');
  await page.getByRole("button", {name:"Đưa vào bản nháp"}).click();
  const current = await mapRead<SpatialLayer>(page, fixture.api + "/layers/" + layer.id);
  const pin = current.source.content_revision;
  const independent = await mapMutation(page, fixture.api + "/sources/" + layer.source_id + "/changesets", "POST", {
    base_content_revision: pin, operation_id: "independent-" + Date.now(), summary: "Independent current update",
    operations: [{op_type:"update",feature_id:"snap_create", properties:{name:"Current writer",measure:"2"}}]
  });
  expect(independent.status).toBe(201);
  await page.getByRole("button", {name:"Lưu thay đổi", exact:true}).click();
  await expect(page.getByText(/Phiên bản nguồn đã thay đổi/)).toBeVisible();
  await expect(page.getByTestId("draft-revision")).toContainText(pin.slice(0,12));
  await expect(page.getByRole("button", {name:"Lưu thay đổi", exact:true})).toBeDisabled();
  expect((await readCurrent(page, fixture, layer.id)).items.find(f=>f.feature_id==="snap_create")?.attributes.name).toBe("Current writer");
});

test("native line and polygon sketches are committed and reread as original CRS geometry", async ({page}) => {
  test.setTimeout(120_000);
  await page.route(/^https?:\/\/(?!(?:127\.0\.0\.1|localhost)(?::|\/|$))/i, route => route.abort());
  await mapSignIn(page);
  const examples = [
    {name:"line", geometry:{type:"LineString", coordinates:[[105.84,21.02],[105.85,21.03]]}},
    {name:"polygon", geometry:{type:"Polygon", coordinates:[[[105.84,21.02],[105.85,21.02],[105.85,21.03],[105.84,21.02]]]}}
  ];
  for (const example of examples) {
    const fixture = await createMapProject(page, Date.now() + "-draw-" + example.name);
    const layer = await importFixture(page, fixture, "draw-" + example.name, example.geometry);
    await page.goto(fixture.root + "/editing");
    const canvas = page.getByTestId("native-edit-canvas");
    await expect(canvas).toBeVisible();
    await page.getByLabel("Bám điểm và đoạn").uncheck();
    await canvas.scrollIntoViewIfNeeded();
    const area = await canvas.boundingBox();
    for (const [x,y] of example.name === "line" ? [[.2,.2],[.7,.25]] : [[.2,.2],[.7,.25],[.6,.65]]) {
      await page.mouse.click(area!.x + area!.width * x!, area!.y + area!.height * y!);
    }
    await page.getByRole("button",{name:"Dùng hình học đã vẽ"}).click();
    const geometry = JSON.parse(await page.getByLabel("Hình học 2D GeoJSON").inputValue()) as {type:string;coordinates:unknown};
    expect(geometry.type).toBe(example.geometry.type);
    await page.getByLabel("Mã đối tượng").fill("drawn_" + example.name);
    await page.getByLabel("Thuộc tính JSON có kiểu").fill('{"name":"Drawn geometry"}');
    await commit(page, "Drawn " + example.name);
    const feature = (await readCurrent(page, fixture, layer.id)).items.find(f=>f.feature_id==="drawn_" + example.name);
    expect(feature?.geometry?.coordinates).toEqual(geometry.coordinates);
    expect(feature?.geometry?.coordinate_reference.code).toBe(4326);
  }
});
