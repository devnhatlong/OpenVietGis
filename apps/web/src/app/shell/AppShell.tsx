import { useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

import { AccountMenu } from "../../features/auth/AccountMenu";
import { AppNavigation } from "./AppNavigation";
import { Breadcrumbs } from "./Breadcrumbs";
import { CommandPalette } from "./CommandPalette";
import { ThemeToggle } from "./ThemeToggle";
import {
  loadShellPreference,
  saveShellPreference
} from "./shell-preference";
import "./app-shell.css";

export function AppShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const isMapWorkstation = /\/projects\/[^/]+\/map$/.test(location.pathname);
  const [collapsed, setCollapsed] = useState(
    () => loadShellPreference().navigationCollapsed
  );
  const effectiveCollapsed = isMapWorkstation ? true : collapsed;

  function toggleNavigation() {
    const next = !collapsed;
    setCollapsed(next);
    saveShellPreference({ navigationCollapsed: next });
  }

  return (
    <div className={[effectiveCollapsed ? "is-collapsed" : "", isMapWorkstation ? "is-map-workstation" : "", "ovg-app-shell"].filter(Boolean).join(" ")}>
      <a className="ovg-skip-link" href="#ovg-app-content">Bỏ qua điều hướng</a>

      <aside className="ovg-app-sidebar">
        <Link className="ovg-app-brand" to="/app" aria-label="OpenVietGIS - Trang làm việc">
          <span className="ovg-brand-mark">OVG</span>
          {effectiveCollapsed ? null : (
            <span><strong>OpenVietGIS</strong><small>Studio 3.0</small></span>
          )}
        </Link>
        <AppNavigation collapsed={effectiveCollapsed} />
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
            <CommandPalette />
            <ThemeToggle />
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
