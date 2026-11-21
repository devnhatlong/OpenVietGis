import type { SaveStatus } from "./save";
import { buildSaveIndicatorView } from "./save-indicator";

export function SaveStateIndicator({
  dirty,
  pendingStatus,
  revision
}: {
  dirty: boolean;
  pendingStatus: SaveStatus | null;
  revision: number;
}) {
  const view = buildSaveIndicatorView({
    dirty,
    pendingStatus,
    revision
  });

  return (
    <div
      className={"map-save-indicator is-" + view.state}
      data-testid="map-save-indicator"
      data-save-state={view.state}
      role="status"
      aria-live="polite"
    >
      <strong data-testid="map-save-status">{view.label}</strong>
      <small>{view.detail}</small>
    </div>
  );
}
