import { useLocation } from "react-router-dom";

const knownLabels: Record<string, string> = {
  app: "Tổng quan",
  organizations: "Tổ chức",
  projects: "Dự án",
  workspaces: "Không gian làm việc",
  membership: "Thành viên & phân quyền",
  map: "Bản đồ",
  spatial: "Dữ liệu GIS",
  transfers: "Nhập / Xuất",
  editing: "Biên tập",
  queries: "Truy vấn",
  processing: "Xử lý",
  cartography: "In ấn",
  "platform-hub": "Công cụ",
  account: "Tài khoản",
  invitations: "Lời mời",
  accept: "Chấp nhận"
};

export function Breadcrumbs() {
  const location = useLocation();
  const segments = location.pathname.split("/").filter(Boolean);
  const readable = segments
    .filter((segment) => knownLabels[segment])
    .map((segment) => knownLabels[segment]);

  return (
    <div className="ovg-breadcrumbs" aria-label="Vị trí hiện tại">
      {readable.length ? readable.join(" / ") : "OpenVietGIS"}
    </div>
  );
}
