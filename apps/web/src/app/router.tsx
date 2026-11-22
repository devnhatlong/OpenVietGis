import {
  Navigate,
  Outlet,
  createBrowserRouter,
  useParams
} from "react-router-dom";

import {
  legacyOrganizationDestination,
  legacyProjectDestination,
  staticLegacyRouteDestinations
} from "./route-contract";
import { SessionBoundary } from "./session/SessionBoundary";
import { AppShell } from "./shell/AppShell";
// Keep direct map navigation free of an import waterfall; other feature screens
// load only when their route is matched. The offline shell precaches every emitted
// static chunk so lazy loading does not require network access after installation.
import { MapWorkspace } from "../features/map/MapWorkspace";

const routerBasename =
  window.location.pathname === "/dev" ||
  window.location.pathname.startsWith("/dev/")
    ? "/dev"
    : undefined;

function RouteLoading() {
  return <main className="ovg-session-bootstrap" role="status" aria-busy="true">Đang tải màn hình…</main>;
}

function AuthenticatedLayout() {
  return (
    <SessionBoundary>
      <AppShell>
        <Outlet />
      </AppShell>
    </SessionBoundary>
  );
}

function LegacyOrganizationRedirect({ suffix = "" }: { suffix?: string }) {
  const { organizationId } = useParams();
  if (!organizationId) return <Navigate replace to="/app" />;

  return (
    <Navigate
      replace
      to={legacyOrganizationDestination(organizationId, suffix)}
    />
  );
}

function LegacyProjectRedirect({ suffix }: { suffix: string }) {
  const { organizationId, projectId } = useParams();
  if (!organizationId || !projectId) return <Navigate replace to="/app" />;

  return (
    <Navigate
      replace
      to={legacyProjectDestination(organizationId, projectId, suffix)}
    />
  );
}

const uxPreviewMode = import.meta.env.VITE_UX_PREVIEW === "true";

export const router = createBrowserRouter(
  [
    {
      path: "/",
      hydrateFallbackElement: <RouteLoading />,
      lazy: async () => uxPreviewMode
        ? { Component: (await import("../features/preview/FrontendPreviewPage")).FrontendPreviewPage }
        : { Component: (await import("../features/landing/LandingPage")).LandingPage }
    },
    { path: "/landing", hydrateFallbackElement: <RouteLoading />, lazy: async () => ({ Component: (await import("../features/landing/LandingPage")).LandingPage }) },
    { path: "/login", hydrateFallbackElement: <RouteLoading />, lazy: async () => ({ Component: (await import("../features/auth/LoginPage")).LoginPage }) },
    { path: "/offline-field/:organizationId/:projectId", hydrateFallbackElement: <RouteLoading />, lazy: async () => ({ Component: (await import("../features/offline/OfflineFieldPage")).OfflineFieldPage }) },

    {
      path: "/app",
      hydrateFallbackElement: <RouteLoading />,
      element: <AuthenticatedLayout />,
      children: [
        { index: true, lazy: async () => ({ Component: (await import("../features/dashboard/AppDashboard")).AppDashboard }) },
        {
          path: "organizations",
          lazy: async () => ({ Component: (await import("../features/organizations/OrganizationHome")).OrganizationHome })
        },
        {
          path: "organizations/:organizationId",
          lazy: async () => ({ Component: (await import("../features/organizations/OrganizationHome")).OrganizationHome })
        },
        {
          path: "organizations/:organizationId/workspaces",
          lazy: async () => ({ Component: (await import("../features/workspaces/WorkspacePage")).WorkspacePage })
        },
        {
          path: "organizations/:organizationId/projects",
          lazy: async () => ({ Component: (await import("../features/projects/ProjectPage")).ProjectPage })
        },
        {
          path: "organizations/:organizationId/projects/:projectId/spatial",
          lazy: async () => ({ Component: (await import("../features/spatial/SpatialCatalogPage")).SpatialCatalogPage })
        },
        {
          path: "organizations/:organizationId/projects/:projectId/map",
          element: <MapWorkspace />
        },
        {
          path: "organizations/:organizationId/projects/:projectId/transfers",
          lazy: async () => ({ Component: (await import("../features/transfers/ImportExportPage")).ImportExportPage })
        },
        {
          path: "organizations/:organizationId/projects/:projectId/editing",
          lazy: async () => ({ Component: (await import("../features/platform/EditingWorkbenchPage")).EditingWorkbenchPage })
        },
        {
          path: "organizations/:organizationId/projects/:projectId/queries",
          lazy: async () => ({ Component: (await import("../features/platform/QueryWorkbenchPage")).QueryWorkbenchPage })
        },
        {
          path: "organizations/:organizationId/projects/:projectId/processing",
          lazy: async () => ({ Component: (await import("../features/platform/ProcessingWorkbenchPage")).ProcessingWorkbenchPage })
        },
        {
          path: "organizations/:organizationId/projects/:projectId/cartography",
          lazy: async () => ({ Component: (await import("../features/platform/CartographyWorkbenchPage")).CartographyWorkbenchPage })
        },
        {
          path: "organizations/:organizationId/projects/:projectId/platform-hub",
          lazy: async () => ({ Component: (await import("../features/platform/PlatformHubPage")).PlatformHubPage })
        },
        {
          path: "organizations/:organizationId/projects/:projectId/extensions/:extensionKey/*",
          lazy: async () => ({ Component: (await import("../features/extensions/ExtensionModulePage")).ExtensionModulePage })
        },
        {
          path: "organizations/:organizationId/membership",
          lazy: async () => ({ Component: (await import("../features/membership/MembershipPage")).MembershipPage })
        },
        { path: "account", lazy: async () => ({ Component: (await import("../features/auth/IdentityPage")).IdentityPage }) },
        {
          path: "invitations/accept",
          lazy: async () => ({ Component: (await import("../features/invitations/InvitationAcceptPage")).InvitationAcceptPage })
        }
      ]
    },

    {
      path: "/organizations/:organizationId",
      element: <LegacyOrganizationRedirect />
    },
    {
      path: "/organizations/:organizationId/workspaces",
      element: <LegacyOrganizationRedirect suffix="/workspaces" />
    },
    {
      path: "/organizations/:organizationId/projects",
      element: <LegacyOrganizationRedirect suffix="/projects" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/spatial",
      element: <LegacyProjectRedirect suffix="/spatial" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/map",
      element: <LegacyProjectRedirect suffix="/map" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/transfers",
      element: <LegacyProjectRedirect suffix="/transfers" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/editing",
      element: <LegacyProjectRedirect suffix="/editing" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/queries",
      element: <LegacyProjectRedirect suffix="/queries" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/processing",
      element: <LegacyProjectRedirect suffix="/processing" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/cartography",
      element: <LegacyProjectRedirect suffix="/cartography" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/platform-hub",
      element: <LegacyProjectRedirect suffix="/platform-hub" />
    },
    {
      path: "/organizations/:organizationId/projects/:projectId/extensions/:extensionKey/*",
      hydrateFallbackElement: <RouteLoading />,
      lazy: async () => ({ Component: (await import("../features/extensions/ExtensionModulePage")).ExtensionModulePage })
    },
    {
      path: "/organizations/:organizationId/membership",
      element: <LegacyOrganizationRedirect suffix="/membership" />
    },
    {
      path: "/identity",
      element: (
        <Navigate
          replace
          to={staticLegacyRouteDestinations["/identity"] ?? "/app/account"}
        />
      )
    },
    {
      path: "/invitations/accept",
      element: (
        <Navigate
          replace
          to={
            staticLegacyRouteDestinations["/invitations/accept"] ??
            "/app/invitations/accept"
          }
        />
      )
    }
  ],
  routerBasename ? { basename: routerBasename } : {}
);
