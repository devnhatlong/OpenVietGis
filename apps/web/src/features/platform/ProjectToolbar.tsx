import { Link } from "react-router-dom";
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
        <Link to={`${base}/spatial`}>Danh mục</Link>
        <Link to={`${base}/transfers`}>Nhập/Xuất</Link>
        <Link to={`${base}/editing`} className={active === "editing" ? "active" : ""}>
          Biên tập
        </Link>
        <Link to={`${base}/queries`} className={active === "queries" ? "active" : ""}>
          Truy vấn
        </Link>
        <Link to={`${base}/processing`} className={active === "processing" ? "active" : ""}>
          Xử lý
        </Link>
        <Link to={`${base}/cartography`} className={active === "cartography" ? "active" : ""}>
          In ấn
        </Link>
        <Link to={`${base}/platform-hub`} className={active === "hub" ? "active" : ""}>
          Công cụ nâng cao
        </Link>
      </nav>
    </header>
  );
}
