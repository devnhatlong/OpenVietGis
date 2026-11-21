import type { OfficialModuleFrontend } from "./types";

type FrontendModule = { moduleFrontend?: OfficialModuleFrontend };

const discovered = import.meta.glob("../../../../../modules/*/frontend/index.tsx", {
  eager: true
}) as Record<string, FrontendModule>;

const registry = new Map<string, OfficialModuleFrontend>();
for (const candidate of Object.values(discovered)) {
  const frontend = candidate.moduleFrontend;
  if (!frontend) continue;
  if (registry.has(frontend.extensionKey)) {
    throw new Error(`Duplicate official module frontend: ${frontend.extensionKey}`);
  }
  registry.set(frontend.extensionKey, frontend);
}

export function getOfficialModuleFrontend(extensionKey: string): OfficialModuleFrontend | undefined {
  return registry.get(extensionKey);
}

export function listOfficialModuleFrontends(): OfficialModuleFrontend[] {
  return [...registry.values()];
}
