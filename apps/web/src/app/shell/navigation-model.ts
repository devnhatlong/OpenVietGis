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
      labelKey: "Bản đồ GIS",
      destination: project + "/map",
      scope: "project",
      availability: "visible",
      short: "BD"
    },
    {
      id: "house-numbering",
      labelKey: "Quản lý Số nhà",
      destination: project + "/extensions/house_numbering",
      scope: "project",
      availability: "visible",
      short: "SN"
    },
    {
      id: "autocad",
      labelKey: "AutoCAD / DXF & COGO",
      destination: project + "/platform-hub?tab=cad",
      scope: "project",
      availability: "visible",
      short: "CAD"
    },
    {
      id: "external-sources",
      labelKey: "Tích hợp Bên thứ 3 (WMS/COG)",
      destination: project + "/platform-hub?tab=external",
      scope: "project",
      availability: "visible",
      short: "T3"
    },
    {
      id: "editing",
      labelKey: "Biên tập GIS (Vẽ/Sửa)",
      destination: project + "/editing",
      scope: "project",
      availability: "visible",
      short: "BT"
    },
    {
      id: "queries",
      labelKey: "Truy vấn & Lọc GIS",
      destination: project + "/queries",
      scope: "project",
      availability: "visible",
      short: "TV"
    },
    {
      id: "processing",
      labelKey: "Phân tích GIS (Buffer/Clip)",
      destination: project + "/processing",
      scope: "project",
      availability: "visible",
      short: "XL"
    },
    {
      id: "cartography",
      labelKey: "Trình bày & In Bản đồ",
      destination: project + "/cartography",
      scope: "project",
      availability: "visible",
      short: "IN"
    },
    {
      id: "spatial",
      labelKey: "Danh mục Lớp & Hệ tọa độ",
      destination: project + "/spatial",
      scope: "project",
      availability: "visible",
      short: "DL"
    },
    {
      id: "transfers",
      labelKey: "Nhập / Xuất (GeoJSON/GPKG)",
      destination: project + "/transfers",
      scope: "project",
      availability: "visible",
      short: "NX"
    },
    {
      id: "field-offline",
      labelKey: "Thực địa & Ngoại tuyến",
      destination: project + "/platform-hub?tab=field",
      scope: "project",
      availability: "visible",
      short: "HT"
    },
    {
      id: "collab",
      labelKey: "Cộng tác & Duyệt thay đổi",
      destination: project + "/platform-hub?tab=collab",
      scope: "project",
      availability: "visible",
      short: "CT"
    },
    {
      id: "tools",
      labelKey: "Quản lý Plugin & Vận hành",
      destination: project + "/platform-hub?tab=extensions",
      scope: "project",
      availability: "visible",
      short: "CC"
    }
  );

  return items;
}
