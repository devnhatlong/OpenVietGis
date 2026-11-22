export type NavigationScope = "global" | "organization" | "project";
export type NavigationAvailability = "visible" | "disabled" | "omitted";
export type NavigationGroup = "workspace" | "gis" | "data" | "admin";

export interface AppNavigationItem {
  id: string;
  labelKey: string;
  destination: string;
  scope: NavigationScope;
  availability: NavigationAvailability;
  short: string;
  group?: NavigationGroup;
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
      short: "TQ",
      group: "workspace"
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
      short: "DA",
      group: "admin"
    },
    {
      id: "workspaces",
      labelKey: "Không gian làm việc",
      destination: org + "/workspaces",
      scope: "organization",
      availability: "visible",
      short: "KG",
      group: "admin"
    },
    {
      id: "membership",
      labelKey: "Thành viên & phân quyền",
      destination: org + "/membership",
      scope: "organization",
      availability: "visible",
      short: "TV",
      group: "admin"
    }
  );

  if (!projectId) return items;

  const project = org + "/projects/" + encodeURIComponent(projectId);
  items.splice(
    1,
    0,
    {
      id: "map",
      labelKey: "Bản đồ GIS",
      destination: project + "/map",
      scope: "project",
      availability: "visible",
      short: "BD",
      group: "workspace"
    },
    {
      id: "autocad",
      labelKey: "AutoCAD / DXF & COGO",
      destination: project + "/map?tool=cad",
      scope: "project",
      availability: "visible",
      short: "CAD",
      group: "gis"
    },
    {
      id: "editing",
      labelKey: "Biên tập GIS (Vẽ/Sửa)",
      destination: project + "/map?tool=editing",
      scope: "project",
      availability: "visible",
      short: "BT",
      group: "gis"
    },
    {
      id: "queries",
      labelKey: "Truy vấn & Lọc GIS",
      destination: project + "/map?tool=queries",
      scope: "project",
      availability: "visible",
      short: "TV",
      group: "gis"
    },
    {
      id: "processing",
      labelKey: "Phân tích (Buffer/Clip)",
      destination: project + "/map?tool=processing",
      scope: "project",
      availability: "visible",
      short: "XL",
      group: "gis"
    },
    {
      id: "cartography",
      labelKey: "Trình bày & In Bản đồ",
      destination: project + "/map?tool=cartography",
      scope: "project",
      availability: "visible",
      short: "IN",
      group: "gis"
    },
    {
      id: "external-sources",
      labelKey: "Tích hợp Bên thứ 3 (WMS/COG)",
      destination: project + "/map?tool=external",
      scope: "project",
      availability: "visible",
      short: "T3",
      group: "data"
    },
    {
      id: "spatial",
      labelKey: "Danh mục Lớp & CRS",
      destination: project + "/map?tool=spatial",
      scope: "project",
      availability: "visible",
      short: "DL",
      group: "data"
    },
    {
      id: "transfers",
      labelKey: "Nhập / Xuất dữ liệu",
      destination: project + "/map?tool=transfers",
      scope: "project",
      availability: "visible",
      short: "NX",
      group: "data"
    },
    {
      id: "field-offline",
      labelKey: "Thực địa & Ngoại tuyến",
      destination: project + "/map?tool=field",
      scope: "project",
      availability: "visible",
      short: "HT",
      group: "data"
    },
    {
      id: "collab",
      labelKey: "Cộng tác & Duyệt",
      destination: project + "/map?tool=collab",
      scope: "project",
      availability: "visible",
      short: "CT",
      group: "admin"
    },
    {
      id: "tools",
      labelKey: "Plugin & Hệ thống",
      destination: project + "/map?tool=extensions",
      scope: "project",
      availability: "visible",
      short: "CC",
      group: "admin"
    }
  );

  return items;
}
