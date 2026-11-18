import {
  ApiError, listSpatialCrsProfiles, getSpatialFeature, readSpatialFeatures, SpatialApiError,
  type SpatialFeature, type SpatialLayer, type SpatialSource
} from "@openvietgis/client-sdk";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient } from "../../app/api";
import { currentProtectedData, protectedQueryOptions } from "../../app/protected-query";
import { availableResponseCrs, crsRegistryKey, crsRegistryMatchesScope } from "./crs-profiles";
import {
  canReadFeatures, createTraversal, FEATURE_PAGE_SIZE,
  featureDetailKey, featureDetailNeedsRevalidation, featurePageKey, featureResponseMatchesScope, formatFeatureValue,
  isStaleFeaturePin, nextFeaturePage, previousFeaturePage, reconcileTraversal,
  restartFeatureTraversal, selectFeature, type FeatureReadScope, type FeatureTraversal
} from "./feature-inspector";

function readError(error: unknown): string {
  if (error instanceof SpatialApiError && error.code === "SOURCE_NOT_READY") {
    return "The source is no longer ready for feature reads.";
  }
  if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
    return "Current access does not permit this feature read.";
  }
  if (error instanceof SpatialApiError && error.code === "TRANSFORMATION_OUT_OF_AREA") {
    return "This geometry is outside the validated area or trusted evidence for the selected coordinate operation. Choose the native CRS or another supported operation.";
  }
  return "Unable to load current feature data.";
}

function FeatureDetail({
  feature, fields
}: { feature: SpatialFeature; fields: SpatialSource["schema"]["fields"] }) {
  const geometry = feature.geometry;
  return (
    <section aria-label="Selected feature detail">
      <h4>Feature {feature.feature_id}</h4>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead><tr><th>Field ID</th><th>Name</th><th>Type</th><th>Value</th></tr></thead>
          <tbody>{fields.map(field => (
            <tr key={field.field_id}>
              <th scope="row">{field.field_id}</th><td>{field.name}</td><td>{field.type}</td>
              <td><code style={{ overflowWrap: "anywhere" }}>{formatFeatureValue(feature.attributes[field.field_id])}</code></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p>Geometry state: {feature.geometry_state}</p>
      {geometry ? (
        <details>
          <summary>{geometry.type} response geometry</summary>
          <p>
            EPSG:{geometry.coordinate_reference.code}, X {geometry.coordinate_reference.x_axis},
            {" "}Y {geometry.coordinate_reference.y_axis} ({geometry.coordinate_reference.unit}).
            Explicit X/Y coordinates; not GeoJSON.
          </p>
          <pre style={{ overflow: "auto", maxHeight: 240 }}>{JSON.stringify(geometry.coordinates, null, 2)}</pre>
        </details>
      ) : null}
    </section>
  );
}

function CurrentFeatureInspector({
  scope, fields, state, setTraversal, reloadMetadata
}: {
  scope: FeatureReadScope; fields: SpatialSource["schema"]["fields"];
  state: FeatureTraversal; setTraversal: (state: FeatureTraversal) => void;
  reloadMetadata: (clearSelection?: boolean) => void;
}) {
  const [detailBlocked, setDetailBlocked] = useState(false);
  const options = {
    content_revision: scope.contentRevision,
    schema_revision: scope.schemaRevision,
    include_geometry: true,
    ...(scope.responseCrs === undefined ? {} : { response_crs: scope.responseCrs })
  };
  const pageQuery = useQuery({
    queryKey: featurePageKey(scope, state.cursor),
    queryFn: () => readSpatialFeatures(apiClient, scope.organizationId, scope.projectId, scope.layerId, {
      ...options, limit: FEATURE_PAGE_SIZE,
      ...(state.cursor === null ? {} : { after_feature_id: state.cursor })
    }),
    enabled: !detailBlocked,
    ...protectedQueryOptions
  });
  const detailQuery = useQuery({
    queryKey: featureDetailKey(scope, state.selected),
    queryFn: () => getSpatialFeature(apiClient, scope.organizationId, scope.projectId,
      scope.layerId, state.selected ?? "", options),
    enabled: state.selected !== null && !detailBlocked,
    ...protectedQueryOptions
  });

  const blocked = featureDetailNeedsRevalidation(detailBlocked, detailQuery.error);
  if (blocked !== detailBlocked) setDetailBlocked(blocked);
  if (blocked) {
    return <>
      <p role="alert">The selected feature or Layer is unavailable. Reload current Layer metadata and restart before showing feature data.</p>
      <button type="button" onClick={() => reloadMetadata(true)}>Revalidate Layer and restart</button>
    </>;
  }
  const stale = isStaleFeaturePin(pageQuery.error) || isStaleFeaturePin(detailQuery.error);
  // A stale response in either read invalidates the whole pinned view: never
  // show an older cached page or detail while retrying the other.
  if (stale) {
    return <>
      <p role="alert">The content or schema changed. Reload current metadata and restart from the first page.</p>
      <button type="button" onClick={() => reloadMetadata()}>Reload revisions and restart</button>
    </>;
  }
  if (detailQuery.error instanceof ApiError && [401, 403].includes(detailQuery.error.status)) {
    return <p role="alert">{readError(detailQuery.error)}</p>;
  }
  const page = currentProtectedData(pageQuery);
  if (!page) {
    return <p role={pageQuery.error ? "alert" : "status"}>
      {pageQuery.error ? readError(pageQuery.error) : "Checking current feature page access…"}
    </p>;
  }
  if (!featureResponseMatchesScope(scope, page.context)) {
    return <p role="alert">The feature page does not match current revisions and scope.</p>;
  }

  const detail = currentProtectedData(detailQuery);
  const matchingDetail = detail && featureResponseMatchesScope(scope, detail.context) &&
    detail.feature.feature_id === state.selected;
  const crs = page.context.response_crs;
  return (
    <>
      <p style={{ overflowWrap: "anywhere" }}>
        {page.context.transformation ? "Transformed" : "Native"} EPSG:{crs?.code} — X {crs?.x_axis}, Y {crs?.y_axis} ({crs?.unit}).<br />
        Content revision: <code>{scope.contentRevision}</code><br />
        Schema revision: <code>{scope.schemaRevision}</code>
      </p>
      {page.context.transformation ? <p role="status">
        Operation: {page.context.transformation.operation_id}. Evidence: {page.context.transformation.evidence_id}.
        {" "}Tolerance: {page.context.transformation.tolerance} {page.context.transformation.tolerance_unit}.
        {" "}{page.context.transformation.validated_area} Native storage is unchanged.
      </p> : null}
      <p>Values use exact JSON representation: strings are quoted, null is distinct from empty text.</p>
      {page.items.length ? (
        <div style={{ overflowX: "auto" }}>
          <table aria-label="Pinned feature page">
            <thead><tr>
              <th>Feature ID</th>
              {fields.map(field => (
                <th key={field.field_id}>{field.name}<br /><small>{field.field_id} — {field.type}</small></th>
              ))}
              <th>Geometry state</th>
            </tr></thead>
            <tbody>{page.items.map(feature => (
              <tr key={feature.feature_id}>
                <th scope="row">
                  <button type="button" aria-pressed={state.selected === feature.feature_id}
                    onClick={() => setTraversal(selectFeature(state, feature.feature_id))}>
                    {feature.feature_id}
                  </button>
                </th>
                {fields.map(field => (
                  <td key={field.field_id}><code>{formatFeatureValue(feature.attributes[field.field_id])}</code></td>
                ))}
                <td>{feature.geometry_state}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      ) : <p>No features on this page.</p>}
      <p role="status">Page {state.history.length + 1} — {page.items.length} feature(s).</p>
      <button type="button" disabled={!state.history.length}
        onClick={() => setTraversal(previousFeaturePage(state))}>Previous features</button>{" "}
      <button type="button" disabled={page.next_after_feature_id === null}
        onClick={() => setTraversal(nextFeaturePage(state, page.next_after_feature_id))}>Next features</button>
      {state.selected !== null ? (
        <section aria-label="Feature selection">
          <p>Selected feature: <code>{state.selected}</code>{" "}
            <button type="button" onClick={() => setTraversal(selectFeature(state, null))}>Clear selection</button>
          </p>
          {matchingDetail ? <FeatureDetail feature={detail.feature} fields={fields} /> :
            <p role={detailQuery.error || detail ? "alert" : "status"}>
              {detailQuery.error ? readError(detailQuery.error)
                  : detail ? "The feature detail does not match the selected ID and current revisions."
                    : "Checking current feature detail access…"}
            </p>}
        </section>
      ) : <p>Select a feature ID to inspect its exact attributes and response geometry.</p>}
    </>
  );
}

export function FeatureInspector({
  accountId, organizationId, projectId, layerId, layer, reloadMetadata
}: {
  accountId: string; organizationId: string; projectId: string; layerId: string;
  layer: SpatialLayer | undefined; reloadMetadata: () => Promise<void>;
}) {
  const [traversal, setTraversal] = useState(createTraversal);
  const [reloading, setReloading] = useState(false);
  const [targetCrs, setTargetCrs] = useState<number | undefined>();
  const registryScope = { accountId, organizationId, projectId };
  const registryQuery = useQuery({ queryKey: crsRegistryKey(registryScope),
    queryFn: () => listSpatialCrsProfiles(apiClient, organizationId, projectId),
    enabled: Boolean(layer), ...protectedQueryOptions });
  const registry = currentProtectedData(registryQuery);
  // The inspector stays mounted while Layer metadata is revalidated so the
  // explicit selection survives stale retries, but no old data stays visible.
  if (!layer || reloading) return null;
  if (layer.id !== layerId || layer.organization_id !== organizationId ||
      layer.project_id !== projectId || layer.source_id !== layer.source.id ||
      layer.source.organization_id !== organizationId || layer.source.project_id !== projectId) {
    return <p role="alert">Current Layer scope does not match the requested Layer.</p>;
  }
  if (!canReadFeatures(layer) || !layer.source.stored_crs) {
    return <p role="status">Feature inspection is not available for this Layer.</p>;
  }

  if (!registry || !crsRegistryMatchesScope(registryScope, registry)) {
    return <p role={registryQuery.error ? "alert" : "status"}>{registryQuery.error
      ? "Unable to verify current CRS profile access." : "Checking current CRS profiles…"}</p>;
  }
  const nativeCrs = layer.source.stored_crs.code;
  const responseOptions = availableResponseCrs(registry, nativeCrs);
  const responseCrs = targetCrs !== undefined && responseOptions.includes(targetCrs) ? targetCrs : nativeCrs;
  const transformation = responseCrs === nativeCrs ? undefined : registry.transformations.find(edge =>
    edge.source_code === nativeCrs && edge.target_code === responseCrs);
  const scope: FeatureReadScope = {
    accountId, organizationId, projectId, layerId, sourceId: layer.source_id,
    contentRevision: layer.source.content_revision,
    schemaRevision: layer.source.schema_revision,
    nativeCrs, responseCrs, ...(transformation ? { transformation } : {})
  };
  const state = reconcileTraversal(traversal, scope);
  // Reconcile before issuing a read, never sending an old cursor under a new pin.
  if (state !== traversal) setTraversal(state);

  return (
    <section aria-label="Feature inspector" style={{ borderTop: "1px solid #aaa", paddingTop: 16, marginTop: 16 }}>
      <h3>Feature inspector</h3>
      <label>Response coordinate reference{" "}
        <select value={responseCrs} onChange={event => setTargetCrs(Number(event.target.value))}>
          {responseOptions.map(code => <option key={code} value={code}>EPSG:{code}{code === nativeCrs ? " (native)" : " (approved operation)"}</option>)}
        </select>
      </label>
      <CurrentFeatureInspector key={[scope.responseCrs, scope.contentRevision, scope.schemaRevision].join(":")} scope={scope} fields={layer.source.schema.fields}
        state={state} setTraversal={setTraversal} reloadMetadata={clearSelection => {
          const restarted = restartFeatureTraversal(state);
          setTraversal(clearSelection ? selectFeature(restarted, null) : restarted);
          setReloading(true);
          void reloadMetadata().finally(() => setReloading(false));
        }} />
    </section>
  );
}
