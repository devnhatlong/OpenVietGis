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
  title
}: ProjectToolbarProps) {
  const base = `/app/organizations/${organizationId}/projects/${projectId}`;
  return (
    <header className="ovg-toolbar">
      <div className="ovg-toolbar-title">
        <span className="ovg-toolbar-kicker">OPENVietGIS STUDIO</span>
        <h1>{title}</h1>
      </div>
      <nav className="ovg-toolbar-links" aria-label="Lối tắt nhanh">
        <Link to={`${base}/map`} className="ovg-pill-link is-primary">Mở Bản đồ GIS</Link>
        <ActiveModuleLinks organizationId={organizationId} projectId={projectId} slot="project_route" />
      </nav>
    </header>
  );
}
