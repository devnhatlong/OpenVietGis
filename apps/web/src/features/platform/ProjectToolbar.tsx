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
  const base = `/organizations/${organizationId}/projects/${projectId}`;
  return (
    <header className="ovg-toolbar">
      <div>
        <strong>OpenVietGIS</strong> · {title}
      </div>
      <nav className="ovg-toolbar-links" aria-label="GIS Workbenches">
        <Link to={`${base}/map`}>Map</Link>
        <Link to={`${base}/spatial`}>Catalog</Link>
        <Link to={`${base}/transfers`}>Import/Export</Link>
        <Link to={`${base}/editing`} className={active === "editing" ? "active" : ""}>
          Editing (R006)
        </Link>
        <Link to={`${base}/queries`} className={active === "queries" ? "active" : ""}>
          Query (R007)
        </Link>
        <Link to={`${base}/processing`} className={active === "processing" ? "active" : ""}>
          Processing (R008)
        </Link>
        <Link to={`${base}/cartography`} className={active === "cartography" ? "active" : ""}>
          Cartography (R009)
        </Link>
        <Link to={`${base}/platform-hub`} className={active === "hub" ? "active" : ""}>
          Platform Hub (R010–R015)
        </Link>
      </nav>
    </header>
  );
}
