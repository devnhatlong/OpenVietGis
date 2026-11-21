export type NavigationScope = "global" | "organization" | "project";
export type NavigationAvailability = "visible" | "disabled" | "omitted";

export interface AppNavigationItem {
  id: string;
  labelKey: string;
  destination: string;
  scope: NavigationScope;
  availability: NavigationAvailability;
  short: string;
}

export function buildNavigationItems(
  organizationId?: string,
  projectId?: string
): AppNavigationItem[] {
  const items: AppNavigationItem[] = [
    {
      id: "overview",
      labelKey: "Tổng quan",
      destination: "/app",
      scope: "global",
      availability: "visible",
      short: "TQ"
    }
  ];

  if (!organizationId) return items;

  const org = "/app/organizations/" + encodeURIComponent(organizationId);
  items.push(
    {
      id: "projects",
      labelKey: "Dự án",
      destination: org + "/projects",
      scope: "organization",
      availability: "visible",
      short: "DA"
    },
    {
      id: "workspaces",
      labelKey: "Không gian làm việc",
      destination: org + "/workspaces",
      scope: "organization",
      availability: "visible",
      short: "KG"
    },
    {
      id: "membership",
      labelKey: "Thành viên & phân quyền",
      destination: org + "/membership",
      scope: "organization",
      availability: "visible",
      short: "TV"
    }
  );

  if (!projectId) return items;

  const project = org + "/projects/" + encodeURIComponent(projectId);
  items.splice(
    2,
    0,
    {
      id: "map",
      labelKey: "Bản đồ",
      destination: project + "/map",
      scope: "project",
      availability: "visible",
      short: "BD"
    },
    {
      id: "spatial",
      labelKey: "Dữ liệu GIS",
      destination: project + "/spatial",
      scope: "project",
      availability: "visible",
      short: "DL"
    },
    {
      id: "transfers",
      labelKey: "Nhập / Xuất",
      destination: project + "/transfers",
      scope: "project",
      availability: "visible",
      short: "NX"
    },
    {
      id: "tools",
      labelKey: "Công cụ",
      destination: project + "/platform-hub",
      scope: "project",
      availability: "visible",
      short: "CC"
    }
  );

  return items;
}
