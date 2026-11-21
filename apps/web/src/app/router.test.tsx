import { describe, expect, it } from "vitest";

import {
  legacyOrganizationDestination,
  legacyProjectDestination,
  staticLegacyRouteDestinations
} from "./route-contract";

describe("legacy route contract", () => {
  it("maps organization routes to canonical /app routes", () => {
    expect(legacyOrganizationDestination("org-1")).toBe(
      "/app/organizations/org-1"
    );
    expect(legacyOrganizationDestination("org-1", "/projects")).toBe(
      "/app/organizations/org-1/projects"
    );
    expect(legacyOrganizationDestination("org-1", "/workspaces")).toBe(
      "/app/organizations/org-1/workspaces"
    );
    expect(legacyOrganizationDestination("org-1", "/membership")).toBe(
      "/app/organizations/org-1/membership"
    );
  });

  it("maps every project capability route without losing ids", () => {
    for (const suffix of [
      "/spatial",
      "/map",
      "/transfers",
      "/editing",
      "/queries",
      "/processing",
      "/cartography",
      "/platform-hub"
    ]) {
      expect(legacyProjectDestination("org-1", "project-1", suffix)).toBe(
        "/app/organizations/org-1/projects/project-1" + suffix
      );
    }
  });

  it("maps static identity and invitation routes", () => {
    expect(staticLegacyRouteDestinations["/identity"]).toBe("/app/account");
    expect(staticLegacyRouteDestinations["/invitations/accept"]).toBe(
      "/app/invitations/accept"
    );
  });
});
