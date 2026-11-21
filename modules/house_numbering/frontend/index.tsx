import type { ComponentType } from "react";
import { HouseNumberingWorkspace } from "./Workspace";
import "./house-numbering.css";

type Props = { organizationId: string; projectId: string };

export const moduleFrontend: {
  extensionKey: string;
  Component: ComponentType<Props>;
} = {
  extensionKey: "house_numbering",
  Component: HouseNumberingWorkspace
};
