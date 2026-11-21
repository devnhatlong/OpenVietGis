import { describe, expect, it } from "vitest";

import { getWorkspaceResponsiveMode } from "./responsive-mode";

describe("workspace responsive mode", () => {
  it("uses the accepted desktop/tablet/mobile thresholds", () => {
    expect(getWorkspaceResponsiveMode(1440)).toBe("desktop");
    expect(getWorkspaceResponsiveMode(1280)).toBe("desktop");
    expect(getWorkspaceResponsiveMode(1279)).toBe("tablet");
    expect(getWorkspaceResponsiveMode(768)).toBe("tablet");
    expect(getWorkspaceResponsiveMode(767)).toBe("mobile");
    expect(getWorkspaceResponsiveMode(375)).toBe("mobile");
  });

  it("fails safely to mobile for invalid widths", () => {
    expect(getWorkspaceResponsiveMode(Number.NaN)).toBe("mobile");
  });
});
