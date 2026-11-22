import { describe, expect, it } from "vitest";
import { geometryStateLabel, mapFeatureValue } from "./feature-presentation";

describe("Vietnamese map feature states", () => {
  it("localizes all spatial geometry enum states and does not invent a known state", () => {
    expect(geometryStateLabel("present")).toBe("Có hình học");
    expect(geometryStateLabel("absent")).toBe("Không có hình học");
    expect(geometryStateLabel("empty")).toBe("Không có hình học");
    expect(geometryStateLabel("invalid")).toBe("Không hợp lệ");
    expect(geometryStateLabel("unsupported")).toBe("Không hỗ trợ hình học");
    expect(geometryStateLabel("unknown-code")).toBe("Trạng thái hình học chưa xác định");
  });

  it("distinguishes missing, explicit null, empty and zero without value coercion", () => {
    expect([undefined, null, "", 0, "0", false].map(mapFeatureValue))
      .toEqual(["Thiếu giá trị", "null", '""', "0", '"0"', "false"]);
  });
});
