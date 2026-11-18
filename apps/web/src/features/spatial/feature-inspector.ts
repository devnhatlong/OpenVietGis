import { SpatialApiError, type SpatialFeatureReadContext } from "@openvietgis/client-sdk";

/** All reads remain in the existing account/owner/Layer cache boundary. */
export interface FeatureReadScope {
  accountId: string;
  organizationId: string;
  projectId: string;
  layerId: string;
  sourceId: string;
  contentRevision: string;
  schemaRevision: string;
  nativeCrs: number;
}

export const FEATURE_PAGE_SIZE = 20;

function featureKey(scope: FeatureReadScope) {
  return [
    "spatial-catalog", scope.accountId, scope.organizationId, scope.projectId, "layers",
    "features", scope.layerId, scope.sourceId, scope.contentRevision, scope.schemaRevision,
    scope.nativeCrs
  ] as const;
}

export function featurePageKey(scope: FeatureReadScope, cursor: string | null) {
  return [...featureKey(scope), "native-page", FEATURE_PAGE_SIZE, cursor] as const;
}

export function featureDetailKey(scope: FeatureReadScope, featureId: string | null) {
  return [...featureKey(scope), "native-detail", featureId] as const;
}

interface FeatureReadGate {
  lifecycle: string;
  source: {
    lifecycle: string;
    validation_state: string;
    schema: { state: string };
    stored_crs: { code: number } | null;
  };
  capabilities: {
    name: string;
    technical_supported: boolean;
    available: boolean;
    actor_authorized: boolean;
    required_permission: string | null;
  }[];
}

export function canReadFeatures(layer: FeatureReadGate | undefined): boolean {
  return Boolean(
    layer && layer.lifecycle === "active" && layer.source.lifecycle === "active" &&
    layer.source.validation_state === "ready" && layer.source.schema.state === "known" &&
    layer.source.stored_crs && [4326, 3857, 4756, 5899].includes(layer.source.stored_crs.code) &&
    layer.capabilities.some(capability =>
      capability.name === "feature_read" && capability.technical_supported &&
      capability.available && capability.actor_authorized &&
      capability.required_permission === "project.read"
    )
  );
}

/** Reject a mismatched context even if a protected query has settled successfully. */
export function featureResponseMatchesScope(
  scope: FeatureReadScope, context: SpatialFeatureReadContext
): boolean {
  const geographic = [4326, 4756].includes(scope.nativeCrs);
  return context.organization_id === scope.organizationId &&
    context.project_id === scope.projectId && context.layer_id === scope.layerId &&
    context.source_id === scope.sourceId && context.content_revision === scope.contentRevision &&
    context.schema_revision === scope.schemaRevision && context.geometry_included &&
    context.transformation === null && context.response_crs?.authority === "EPSG" &&
    context.response_crs.code === scope.nativeCrs && context.response_crs.coordinate_order === "xy" &&
    context.response_crs.x_axis === (geographic ? "longitude" : "easting") &&
    context.response_crs.y_axis === (geographic ? "latitude" : "northing") &&
    context.response_crs.unit === (geographic ? "degree" : "metre");
}

export interface FeatureTraversal {
  scope: FeatureReadScope | null;
  cursor: string | null;
  history: (string | null)[];
  selected: string | null;
}

export function createTraversal(): FeatureTraversal {
  return { scope: null, cursor: null, history: [], selected: null };
}

export function restartFeatureTraversal(state: FeatureTraversal): FeatureTraversal {
  // Keep the explicit selection even when it no longer exists at the new pin.
  return { ...state, cursor: null, history: [] };
}

export function reconcileTraversal(
  state: FeatureTraversal, scope: FeatureReadScope
): FeatureTraversal {
  const prior = state.scope;
  if (!prior || prior.accountId !== scope.accountId || prior.organizationId !== scope.organizationId ||
      prior.projectId !== scope.projectId || prior.layerId !== scope.layerId ||
      prior.sourceId !== scope.sourceId) {
    return { ...createTraversal(), scope };
  }
  if (prior.contentRevision !== scope.contentRevision || prior.schemaRevision !== scope.schemaRevision ||
      prior.nativeCrs !== scope.nativeCrs) {
    return { ...restartFeatureTraversal(state), scope };
  }
  return state;
}

export function nextFeaturePage(state: FeatureTraversal, cursor: string | null): FeatureTraversal {
  if (cursor === null) return state;
  return { ...state, cursor, history: [...state.history, state.cursor] };
}

export function previousFeaturePage(state: FeatureTraversal): FeatureTraversal {
  if (!state.history.length) return state;
  return { ...state, cursor: state.history[state.history.length - 1] ?? null, history: state.history.slice(0, -1) };
}

export function selectFeature(state: FeatureTraversal, featureId: string | null): FeatureTraversal {
  return { ...state, selected: featureId };
}

export function formatFeatureValue(value: string | number | boolean | null | undefined): string {
  // JSON preserves the exact decimal/timestamp strings, distinguishing null,
  // empty text, a text "0" and an integer 0. No numeric or Date coercion.
  return value === undefined ? "Missing value" : JSON.stringify(value);
}

export function isStaleFeaturePin(error: unknown): boolean {
  return error instanceof SpatialApiError && error.status === 409 && error.code === "STALE_READ_PIN";
}
