const KEY = "openvietgis:shell-preferences";

export interface ShellPreference {
  navigationCollapsed: boolean;
}

export function loadShellPreference(): ShellPreference {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { navigationCollapsed: false };
    const value = JSON.parse(raw) as Partial<ShellPreference>;
    return { navigationCollapsed: value.navigationCollapsed === true };
  } catch {
    return { navigationCollapsed: false };
  }
}

export function saveShellPreference(preference: ShellPreference): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(preference));
  } catch {
    // Preferences are non-critical and must never block application access.
  }
}
