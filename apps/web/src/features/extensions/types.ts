import type { ComponentType } from "react";

export interface OfficialModuleFrontendProps {
  organizationId: string;
  projectId: string;
}

export interface OfficialModuleFrontend {
  extensionKey: string;
  Component: ComponentType<OfficialModuleFrontendProps>;
}
