import { Link } from "react-router-dom";
import { ActiveModuleLinks } from "../extensions/ActiveModuleLinks";
import "./platform.css";

interface ProjectToolbarProps {
  organizationId: string;
  projectId: string;
  active: "editing" | "queries" | "processing" | "cartography" | "hub";
  title: string;
}

export function ProjectToolbar({
  organizationId,
  projectId,
  active,
  title
}: ProjectToolbarProps) {
  const base = `/app/organizations/${organizationId}/projects/${projectId}`;
  return (
    <header className="ovg-toolbar">
      <div>
        <strong>OpenVietGIS</strong> · {title}
      </div>
      <nav className="ovg-toolbar-links" aria-label="GIS Workbenches">
        <Link to={`${base}/map`}>Bản đồ</Link>
        <Link to={`${base}/extensions/house_numbering`}>Số nhà</Link>
        <Link to={`${base}/platform-hub?tab=cad`}>AutoCAD & COGO</Link>
        <Link to={`${base}/platform-hub?tab=external`}>Tích hợp Bên thứ 3 (WMS/COG)</Link>
        <Link to={`${base}/editing`} className={active === "editing" ? "active" : ""}>
          Biên tập GIS
        </Link>
        <Link to={`${base}/queries`} className={active === "queries" ? "active" : ""}>
          Truy vấn GIS
        </Link>
        <Link to={`${base}/processing`} className={active === "processing" ? "active" : ""}>
          Xử lý (Buffer/Clip)
        </Link>
        <Link to={`${base}/cartography`} className={active === "cartography" ? "active" : ""}>
          In ấn Bản đồ
        </Link>
        <Link to={`${base}/transfers`}>Nhập/Xuất</Link>
        <Link to={`${base}/spatial`}>Danh mục & CRS</Link>
        <Link to={`${base}/platform-hub?tab=field`}>Thực địa Offline</Link>
        <ActiveModuleLinks organizationId={organizationId} projectId={projectId} slot="project_route" />
      </nav>
    </header>
  );
}
