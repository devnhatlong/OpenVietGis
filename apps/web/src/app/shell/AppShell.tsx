import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { AccountMenu } from "../../features/auth/AccountMenu";
import { AppNavigation } from "./AppNavigation";
import { Breadcrumbs } from "./Breadcrumbs";
import {
  loadShellPreference,
  saveShellPreference
} from "./shell-preference";
import "./app-shell.css";

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(
    () => loadShellPreference().navigationCollapsed
  );

  function toggleNavigation() {
    const next = !collapsed;
    setCollapsed(next);
    saveShellPreference({ navigationCollapsed: next });
  }

  return (
    <div className={collapsed ? "ovg-app-shell is-collapsed" : "ovg-app-shell"}>
      <a className="ovg-skip-link" href="#ovg-app-content">Bỏ qua điều hướng</a>

      <aside className="ovg-app-sidebar">
        <Link className="ovg-app-brand" to="/app" aria-label="OpenVietGIS - Trang làm việc">
          <span className="ovg-brand-mark">OVG</span>
          {collapsed ? null : (
            <span><strong>OpenVietGIS</strong><small>GIS Workspace</small></span>
          )}
        </Link>
        <AppNavigation collapsed={collapsed} />
        <button
          className="ovg-sidebar-toggle"
          type="button"
          onClick={toggleNavigation}
          aria-label={collapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}
          aria-expanded={!collapsed}
        >
          <span aria-hidden="true">{collapsed ? "→" : "←"}</span>
          {collapsed ? null : <span>Thu gọn</span>}
        </button>
      </aside>

      <div className="ovg-app-stage">
        <header className="ovg-app-topbar">
          <Breadcrumbs />
          <div className="ovg-app-topbar-actions">
            <span className="ovg-command-hint" title="Command palette sẽ được mở rộng theo capability">
              Ctrl K · Lệnh nhanh
            </span>
            <AccountMenu />
          </div>
        </header>
        <div id="ovg-app-content" className="ovg-app-content">
          {children}
        </div>
      </div>
    </div>
  );
}
