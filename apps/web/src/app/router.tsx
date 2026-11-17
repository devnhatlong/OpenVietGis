import { createBrowserRouter } from "react-router-dom";

import { IdentityPage } from "../features/auth/IdentityPage";
import { OrganizationHome } from "../features/organizations/OrganizationHome";
import { FoundationPage } from "./FoundationPage";

export const router = createBrowserRouter([
  { path: "/", element: <OrganizationHome /> },
  { path: "/organizations/:organizationId", element: <OrganizationHome /> },
  { path: "/identity", element: <IdentityPage /> },
  { path: "/foundation", element: <FoundationPage /> }
]);
