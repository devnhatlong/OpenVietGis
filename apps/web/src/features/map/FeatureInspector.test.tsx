import type { SpatialFeatureDetail, SpatialLayer } from "@openvietgis/client-sdk";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FeatureInspector } from "./FeatureInspector";

const layer = {
  name: "Lớp điểm",
  source: { schema: { fields: [] }, source_crs: { code: 4326 }, stored_crs: { code: 4326 } }
} as unknown as SpatialLayer;
const detail = {
  context: { content_revision: "observed-content", schema_revision: "observed-schema", response_crs: { code: 4326 } },
  feature: { feature_id: "point-1", geometry_state: "available", attributes: {} }
} as unknown as SpatialFeatureDetail;

describe("map feature inspector revision", () => {
  it("shows observed feature response revisions only inside a secondary labeled details surface", () => {
    const html = renderToStaticMarkup(<FeatureInspector layer={layer} detail={detail} focus="point-1" count={1} error={null}/>);
    expect(html).toContain('<details class="map-muted" data-testid="inspector-observed-revision">');
    expect(html).toContain("Phiên bản dữ liệu đã đọc");
    expect(html).toContain("observed-content");
    expect(html).toContain("observed-schema");
  });

  it("does not disclose old detail revisions after selection or authorization is lost", () => {
    for (const props of [
      { focus: null, error: null },
      { focus: "point-1", error: "Không đủ quyền" }
    ]) {
      const html = renderToStaticMarkup(<FeatureInspector layer={layer} detail={detail} count={1} {...props}/>);
      expect(html).not.toContain("observed-content");
      expect(html).not.toContain("observed-schema");
    }
  });
});
