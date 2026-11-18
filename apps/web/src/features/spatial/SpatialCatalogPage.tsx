import {
  ApiError,
  createSpatialLayer,
  getSpatialLayer,
  listSpatialLayers,
  renameSpatialLayer,
  retireSpatialLayer,
  getProject,
  getSpatialSource,
  listSpatialSources,
  loadCsrfToken,
  registerSpatialSource,
  retireSpatialSource,
  SpatialApiError,
  updateSpatialSource,
  type SpatialSource,
  type SpatialLayer,
  type SpatialLayerMutation,
  type SpatialDeclaredCrs,
  type SpatialSourceMutation
} from "@openvietgis/client-sdk";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { apiClient } from "../../app/api";
import { currentProtectedData, protectedQueryOptions } from "../../app/protected-query";
import { FreshAccount } from "../auth/FreshAccount";

const fixtureSuggestions = [
  "reference_points_4326", "reference_lines_4326", "reference_polygons_4326",
  "reference_points_3857", "reference_points_4756", "reference_points_5899",
  "reference_empty_4326", "reference_correctable_crs"
] as const;

function safeError(error: unknown): string {
  if (error instanceof SpatialApiError) {
    switch (error.code) {
      case "STALE_LAYER_REVISION": return "The Layer changed. Review the latest revision before retrying.";
      case "SOURCE_NOT_READY": return "The source is not ready for Layer creation.";
      case "STALE_CATALOG_REVISION": return "The source changed. Review the latest revision before retrying.";
      case "ACTIVE_LAYER_DEPENDENCIES": return "Retire active Layers before retiring the source.";
      case "SOURCE_ALREADY_REGISTERED": return "This reference is already registered in this Project, including retired sources.";
      case "PROJECT_NOT_WRITABLE": return "This Project is read-only.";
      case "UNKNOWN_REFERENCE_KEY": return "This logical reference key is not allowlisted.";
      case "CRS_CORRECTION_UNVERIFIED": return "Independent evidence does not verify the proposed declaration.";
      case "NO_CHANGES": return "No material change was provided.";
      default: return "The spatial operation could not be completed.";
    }
  }
  if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
    return "Current access does not permit this operation.";
  }
  return "The spatial operation could not be completed.";
}

function CRSDescription({ label, crs }: {
  label: string;
  crs: SpatialSource["source_crs"];
}) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{crs ? <>
        EPSG:{crs.code} — {crs.name} ({crs.disposition})<br />
        Native order: {crs.native_axes.join(", ")}; application order: X {crs.x_axis}, Y {crs.y_axis} ({crs.unit})
      </> : "Unknown"}</dd>
    </div>
  );
}

function SourceMetadata({ source }: { source: SpatialSource }) {
  const extent = source.extent;
  return (
    <section aria-label="Source metadata" style={{ overflowWrap: "anywhere" }}>
      <h2>{source.name}</h2>
      <dl>
        <dt>Source ID</dt><dd>{source.id}</dd>
        <dt>Validation</dt><dd>{source.validation_state}</dd>
        {source.validation_reason ? <>
          <dt>Reason</dt><dd>{source.validation_reason.code}: {source.validation_reason.message}</dd>
        </> : null}
        <CRSDescription label="Declared CRS" crs={source.source_crs} />
        <CRSDescription label="Stored native CRS" crs={source.stored_crs} />
        <dt>Feature count</dt><dd>{source.feature_count_state === "known" ? source.feature_count : "Unavailable"}</dd>
        <dt>Native extent</dt>
        <dd>{extent ? <>
          ({extent.min_x}, {extent.min_y}) – ({extent.max_x}, {extent.max_y})<br />
          EPSG:{extent.coordinate_reference.code}, {extent.coordinate_reference.unit}, X/Y
        </> : source.extent_state === "empty" ? "Empty source (no extent)" : "Unavailable"}</dd>
        <dt>Schema</dt><dd>{source.schema.state} — {source.schema.geometry_family}, {source.schema.dimensions}</dd>
        <dt>Reference key</dt><dd>{source.provenance.reference_key}</dd>
        <dt>Fixture version</dt><dd>{source.provenance.fixture_version}</dd>
        <dt>Manifest digest</dt><dd><code>{source.provenance.manifest_digest}</code></dd>
        <dt>Catalog revision</dt><dd>{source.catalog_revision}</dd>
        <dt>Content revision</dt><dd><code>{source.content_revision}</code></dd>
        <dt>Schema revision</dt><dd><code>{source.schema_revision}</code></dd>
      </dl>
      <h3>Fields</h3>
      {source.schema.state === "unavailable" ? <p>Schema unavailable.</p> :
      source.schema.fields.length === 0 ? <p>No fields.</p> :
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead><tr><th>ID</th><th>Name</th><th>Type</th><th>Nullable</th></tr></thead>
            <tbody>{source.schema.fields.map(field => (
              <tr key={field.field_id}>
                <td>{field.field_id}</td><td>{field.name}</td><td>{field.type}</td>
                <td>{field.nullable ? "Yes" : "No"}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      }
    </section>
  );
}


type LayerCommand =
  | { kind: "create"; sourceId: string; name: string }
  | { kind: "rename"; layer: SpatialLayer; name: string }
  | { kind: "retire"; layer: SpatialLayer };

function LayerPanel({ organizationId, projectId, accountId, source, writable }: {
  organizationId: string; projectId: string; accountId: string;
  source: SpatialSource | undefined; writable: boolean;
}) {
  const queryClient = useQueryClient();
  const prefix = ["spatial-catalog", accountId, organizationId, projectId, "layers"];
  const [cursor, setCursor] = useState<string | undefined>();
  const [history, setHistory] = useState<(string | undefined)[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [rename, setRename] = useState("");
  const [confirmRetire, setConfirmRetire] = useState(false);
  const listQuery = useQuery({
    queryKey: [...prefix, "list", cursor ?? null],
    queryFn: () => listSpatialLayers(apiClient, organizationId, projectId, {
      limit: 20, ...(cursor === undefined ? {} : { after_id: cursor })
    }),
    ...protectedQueryOptions
  });
  const layers = currentProtectedData(listQuery);
  const detailQuery = useQuery({
    queryKey: [...prefix, "detail", selected],
    queryFn: () => getSpatialLayer(apiClient, organizationId, projectId, selected ?? ""),
    enabled: selected !== null && layers !== undefined,
    ...protectedQueryOptions
  });
  const detail = currentProtectedData(detailQuery);
  const command = useMutation<SpatialLayerMutation, Error, LayerCommand>({
    mutationFn: async input => {
      await loadCsrfToken(apiClient);
      switch (input.kind) {
        case "create": return createSpatialLayer(apiClient, organizationId, projectId, {
          source_id: input.sourceId, name: input.name
        });
        case "rename": return renameSpatialLayer(apiClient, organizationId, projectId, input.layer.id, {
          expected_revision: input.layer.layer_revision, name: input.name
        });
        case "retire": return retireSpatialLayer(apiClient, organizationId, projectId, input.layer.id, {
          expected_revision: input.layer.layer_revision
        });
      }
    },
    onSuccess: async (_result, input) => {
      if (input.kind === "create") {
        setName(""); setCursor(undefined); setHistory([]);
      }
      if (input.kind === "retire") setSelected(null);
      setRename(""); setConfirmRetire(false);
      await queryClient.invalidateQueries({ queryKey: prefix });
    },
    onError: async () => {
      setConfirmRetire(false);
      await queryClient.invalidateQueries({ queryKey: prefix });
      // Auth/project denial needs a fresh check of the parent gate too.
      await queryClient.invalidateQueries({
        queryKey: ["spatial-project", accountId, organizationId, projectId]
      });
    }
  });
  const editable = writable && !command.isPending && layers !== undefined;
  function choose(id: string | null) {
    setSelected(id); setRename(""); setConfirmRetire(false); command.reset();
  }
  return (
    <section aria-label="Layer catalog" style={{ borderTop: "1px solid #aaa", marginTop: 32, paddingTop: 16 }}>
      <h2>Layers</h2>
      <p>Multiple Layers can reference one registered source without copying feature data.</p>
      {writable ? (
        <form onSubmit={event => {
          event.preventDefault();
          if (editable && source?.validation_state === "ready" && name.trim()) {
            command.mutate({ kind: "create", sourceId: source.id, name: name.trim() });
          }
        }}>
          <fieldset disabled={!editable || source?.validation_state !== "ready"}>
            <legend>Create a Layer from the selected source</legend>
            <p>{source ? source.name + " — " + source.validation_state : "Select a ready source above."}</p>
            <label>Layer name{" "}
              <input value={name} onChange={event => setName(event.target.value)} required maxLength={200} />
            </label>{" "}
            <button type="submit" disabled={!name.trim()}>Create Layer</button>
          </fieldset>
        </form>
      ) : null}
      {command.error ? <p role="alert">{safeError(command.error)}</p> : null}
      {!layers ? <p role={listQuery.error ? "alert" : "status"}>
        {listQuery.error ? "Unable to load current Layer access." : "Checking Layer access…"}
      </p> : <>
        {layers.items.length ? (
          <ul aria-label="Registered Layers">
            {layers.items.map(layer => (
              <li key={layer.id}>
                <button type="button" onClick={() => choose(layer.id)}
                  disabled={command.isPending} aria-pressed={selected === layer.id}>
                  {layer.name} — {layer.source.name} — revision {layer.layer_revision}
                </button>
              </li>
            ))}
          </ul>
        ) : <p>No active Layers.</p>}
        <button type="button" disabled={command.isPending || history.length === 0} onClick={() => {
          setCursor(history[history.length - 1]); setHistory(history.slice(0, -1)); choose(null);
        }}>Previous Layers</button>{" "}
        <button type="button" disabled={command.isPending || !layers.next_after_id} onClick={() => {
          if (layers.next_after_id) {
            setHistory([...history, cursor]); setCursor(layers.next_after_id); choose(null);
          }
        }}>Next Layers</button>
        {selected !== null ? !detail ? <p role={detailQuery.error ? "alert" : "status"}>
          {detailQuery.error ? "Unable to load current Layer access." : "Checking Layer metadata…"}
        </p> : (
          <section aria-label="Layer metadata">
            <h3>{detail.name}</h3>
            <dl style={{ overflowWrap: "anywhere" }}>
              <dt>Layer ID</dt><dd>{detail.id}</dd>
              <dt>Layer revision</dt><dd>{detail.layer_revision}</dd>
              <dt>Source</dt><dd>{detail.source.name} ({detail.source_id})</dd>
              <dt>Source state</dt><dd>{detail.source.validation_state}</dd>
            </dl>
            <h4>Capabilities</h4>
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead><tr><th>Operation</th><th>Supported</th><th>Available</th><th>Required permission</th><th>Authorized</th></tr></thead>
                <tbody>{detail.capabilities.map(capability => (
                  <tr key={capability.name}>
                    <td>{capability.name}</td><td>{capability.technical_supported ? "Yes" : "No"}</td>
                    <td>{capability.available ? "Yes" : "No"}</td><td>{capability.required_permission ?? "None"}</td>
                    <td>{capability.actor_authorized ? "Yes" : "No"}</td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <details>
              <summary>Current source schema, CRS and revisions</summary>
              <SourceMetadata source={detail.source} />
            </details>
            {writable ? <fieldset disabled={!editable}>
              <legend>Layer metadata controls</legend>
              <form onSubmit={event => {
                event.preventDefault();
                if (editable && rename.trim()) command.mutate({ kind: "rename", layer: detail, name: rename.trim() });
              }}>
                <label>New Layer name{" "}
                  <input value={rename} onChange={event => setRename(event.target.value)} required maxLength={200} />
                </label>{" "}
                <button type="submit" disabled={!rename.trim()}>Rename Layer</button>
              </form>
              {!confirmRetire ? <button type="button" onClick={() => setConfirmRetire(true)}>Retire Layer</button> : <>
                <p>Retirement hides this Layer. Its source and other Layers remain unchanged.</p>
                <button type="button" onClick={() => command.mutate({ kind: "retire", layer: detail })}>Confirm Layer retirement</button>{" "}
                <button type="button" onClick={() => setConfirmRetire(false)}>Cancel</button>
              </>}
            </fieldset> : null}
          </section>
        ) : null}
      </>}
    </section>
  );
}

type CatalogCommand =
  | { kind: "register"; reference_key: string; name: string }
  | { kind: "rename"; source: SpatialSource; name: string }
  | { kind: "correct"; source: SpatialSource; declaration: SpatialDeclaredCrs }
  | { kind: "retire"; source: SpatialSource };

function CatalogView({ organizationId, projectId, accountId }: {
  organizationId: string; projectId: string; accountId: string;
}) {
  const queryClient = useQueryClient();
  const [afterId, setAfterId] = useState<string | undefined>();
  const [history, setHistory] = useState<(string | undefined)[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [referenceKey, setReferenceKey] = useState("");
  const [newName, setNewName] = useState("");
  const [rename, setRename] = useState("");
  const [crs, setCrs] = useState("4326");
  const [confirmRetire, setConfirmRetire] = useState(false);
  const queryPrefix = ["spatial-catalog", accountId, organizationId, projectId];
  const projectQuery = useQuery({
    queryKey: ["spatial-project", accountId, organizationId, projectId],
    queryFn: () => getProject(apiClient, organizationId, projectId),
    ...protectedQueryOptions
  });
  const project = currentProtectedData(projectQuery);
  const listQuery = useQuery({
    queryKey: [...queryPrefix, "list", afterId ?? null],
    queryFn: () => listSpatialSources(apiClient, organizationId, projectId, {
      limit: 20, ...(afterId === undefined ? {} : { after_id: afterId })
    }),
    ...protectedQueryOptions
  });
  const catalog = currentProtectedData(listQuery);
  const detailQuery = useQuery({
    queryKey: [...queryPrefix, "detail", selected],
    queryFn: () => getSpatialSource(apiClient, organizationId, projectId, selected ?? ""),
    enabled: selected !== null && project !== undefined && catalog !== undefined,
    ...protectedQueryOptions
  });
  const detail = currentProtectedData(detailQuery);
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryPrefix }),
      queryClient.invalidateQueries({ queryKey: ["spatial-project", accountId, organizationId, projectId] })
    ]);
  };
  const command = useMutation<SpatialSourceMutation, Error, CatalogCommand>({
    mutationFn: async (input) => {
      await loadCsrfToken(apiClient);
      switch (input.kind) {
        case "register": return registerSpatialSource(apiClient, organizationId, projectId, {
          reference_key: input.reference_key, name: input.name
        });
        case "rename": return updateSpatialSource(apiClient, organizationId, projectId, input.source.id, {
          expected_revision: input.source.catalog_revision, name: input.name
        });
        case "correct": return updateSpatialSource(apiClient, organizationId, projectId, input.source.id, {
          expected_revision: input.source.catalog_revision, declared_crs: input.declaration
        });
        case "retire": return retireSpatialSource(apiClient, organizationId, projectId, input.source.id, {
          expected_revision: input.source.catalog_revision
        });
      }
    },
    onSuccess: async (_result, input) => {
      if (input.kind === "register") {
        setReferenceKey(""); setNewName(""); setAfterId(undefined); setHistory([]);
      }
      if (input.kind === "retire") setSelected(null);
      setRename(""); setConfirmRetire(false);
      await refresh();
    },
    onError: async () => {
      setConfirmRetire(false);
      await refresh();
    }
  });
  function selectSource(id: string | null) {
    setSelected(id); setRename(""); setConfirmRetire(false); command.reset();
  }
  function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (referenceKey && newName.trim() && project?.status === "active") {
      command.mutate({ kind: "register", reference_key: referenceKey, name: newName.trim() });
    }
  }
  const writable = project?.status === "active" && !command.isPending;

  return (
    <main style={{ maxWidth: 1100, margin: "32px auto", padding: "0 16px", fontFamily: "system-ui, sans-serif" }}>
      <p><Link to={"/organizations/" + encodeURIComponent(organizationId) + "/projects"}>← Projects</Link></p>
      <h1>Spatial source catalog</h1>
      <p>Register and inspect trusted reference fixtures. No uploads or external data connections.</p>
      {!project || !catalog ? (
        <p role={projectQuery.error || listQuery.error ? "alert" : "status"}>
          {projectQuery.error || listQuery.error ? "Unable to load current Project access." : "Checking Project access…"}
        </p>
      ) : (
        <>
          <p><strong>{project.name}</strong> · {project.status}</p>
          {project.status === "archived" ? <p>Archived Project — read-only.</p> : null}
          {project.status === "active" ? (
            <form onSubmit={register}>
              <fieldset disabled={!writable}>
                <legend>Register a reference source</legend>
                <label>Logical reference key{" "}
                  <input value={referenceKey} onChange={event => setReferenceKey(event.target.value)}
                    list="reference-fixtures" required pattern="[a-z0-9_]+" maxLength={100} />
                </label>
                <datalist id="reference-fixtures">
                  {fixtureSuggestions.map(key => <option key={key} value={key} />)}
                </datalist>
                {" "}<label>Source name{" "}
                  <input value={newName} onChange={event => setNewName(event.target.value)}
                    required maxLength={200} />
                </label>
                {" "}<button type="submit" disabled={!newName.trim()}>Register</button>
              </fieldset>
            </form>
          ) : null}
          {command.error ? <p role="alert">{safeError(command.error)}</p> : null}
          <h2>Registered sources</h2>
          {catalog.items.length === 0 ? <p>No active sources.</p> : (
            <ul aria-label="Registered sources">
              {catalog.items.map(source => (
                <li key={source.id}>
                  <button type="button" onClick={() => selectSource(source.id)}
                    disabled={command.isPending} aria-pressed={selected === source.id}>
                    {source.name} — {source.validation_state}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div>
            <button type="button" disabled={command.isPending || history.length === 0} onClick={() => {
              setAfterId(history[history.length - 1]); setHistory(history.slice(0, -1)); selectSource(null);
            }}>Previous</button>{" "}
            <button type="button" disabled={command.isPending || !catalog.next_after_id} onClick={() => {
              if (catalog.next_after_id) {
                setHistory([...history, afterId]); setAfterId(catalog.next_after_id); selectSource(null);
              }
            }}>Next</button>
          </div>
          {selected !== null ? !detail ? <p role={detailQuery.error ? "alert" : "status"}>
            {detailQuery.error ? "Unable to load current source access." : "Checking source metadata…"}
          </p> : <>
            <SourceMetadata source={detail} />
            {project.status === "active" ? (
              <fieldset disabled={!writable}>
                <legend>Source metadata controls</legend>
                <form onSubmit={event => {
                  event.preventDefault();
                  if (rename.trim()) command.mutate({ kind: "rename", source: detail, name: rename.trim() });
                }}>
                  <label>New source name{" "}
                    <input value={rename} onChange={event => setRename(event.target.value)} maxLength={200} required />
                  </label>{" "}
                  <button type="submit" disabled={!rename.trim()}>Rename</button>
                </form>
                {detail.validation_state !== "ready" ? (
                  <form onSubmit={event => {
                    event.preventDefault();
                    command.mutate({
                      kind: "correct", source: detail,
                      declaration: { authority: "EPSG", code: Number(crs), coordinate_order: "xy" }
                    });
                  }}>
                    <label>Correct declared CRS (independent evidence required){" "}
                      <select value={crs} onChange={event => setCrs(event.target.value)}>
                        {[4326, 3857, 4756, 5899].map(code => <option key={code} value={code}>EPSG:{code}</option>)}
                      </select>
                    </label>{" "}<button type="submit">Verify and correct</button>
                  </form>
                ) : null}
                {!confirmRetire ? <button type="button" onClick={() => setConfirmRetire(true)}>Retire source</button> :
                  <div>
                    <p>Retirement hides this source from ordinary reads. Active Layers must be retired first.</p>
                    <button type="button" onClick={() => command.mutate({ kind: "retire", source: detail })}>Confirm retirement</button>{" "}
                    <button type="button" onClick={() => setConfirmRetire(false)}>Cancel</button>
                  </div>
                }
              </fieldset>
            ) : null}
          </> : null}
          <LayerPanel organizationId={organizationId} projectId={projectId}
            accountId={accountId} source={detail} writable={writable} />
        </>
      )}
    </main>
  );
}

export function SpatialCatalogPage() {
  const { organizationId, projectId } = useParams();
  if (!organizationId || !projectId) return <p role="alert">Project context is missing.</p>;
  return (
    <FreshAccount key={organizationId + ":" + projectId}>
      {account => <CatalogView
        key={account.id + ":" + organizationId + ":" + projectId}
        organizationId={organizationId} projectId={projectId} accountId={account.id}
      />}
    </FreshAccount>
  );
}
