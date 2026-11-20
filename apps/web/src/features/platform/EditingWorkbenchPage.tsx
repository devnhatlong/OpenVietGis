import {
  commitChangeset,
  listChangesets,
  listSpatialSources,
  loadCsrfToken,
  revertChangeset,
  type Changeset
} from "@openvietgis/client-sdk";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { apiClient } from "../../app/api";
import { ProjectToolbar } from "./ProjectToolbar";

interface DraftOp {
  op_type: "create" | "update" | "delete";
  feature_id: string;
  geometry?: Record<string, unknown> | null;
  properties?: Record<string, unknown> | null;
}

export function EditingWorkbenchPage() {
  const { organizationId = "", projectId = "" } = useParams();
  const qc = useQueryClient();
  const [selectedSourceId, setSelectedSourceId] = useState("");
  const [featureId, setFeatureId] = useState("feat_new_1");
  const [opType, setOpType] = useState<"create" | "update" | "delete">("create");
  const [geomJson, setGeomJson] = useState(
    '{"type":"Point","coordinates":[105.85,21.02]}'
  );
  const [propsJson, setPropsJson] = useState("{}");
  const [summary, setSummary] = useState("Interactive feature edit");
  const [draft, setDraft] = useState<DraftOp[]>([]);
  const [redoStack, setRedoStack] = useState<DraftOp[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sourcesQuery = useQuery({
    queryKey: ["r006", organizationId, projectId, "sources"],
    queryFn: () => listSpatialSources(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });

  const editableSources = (sourcesQuery.data?.items ?? []).filter(
    (s) => s.kind !== "reference_fixture" && s.lifecycle === "active"
  );
  const activeSource =
    editableSources.find((s) => s.id === selectedSourceId) ?? editableSources[0];

  const historyQuery = useQuery({
    queryKey: ["r006", organizationId, projectId, "changesets", activeSource?.id],
    queryFn: () => listChangesets(apiClient, organizationId, projectId, activeSource!.id),
    enabled: Boolean(activeSource?.id)
  });

  function stageOperation(): void {
    setError(null);
    try {
      const op: DraftOp = {
        op_type: opType,
        feature_id: featureId.trim()
      };
      if (opType !== "delete") {
        op.geometry = geomJson.trim() ? (JSON.parse(geomJson) as Record<string, unknown>) : null;
        op.properties = propsJson.trim() ? (JSON.parse(propsJson) as Record<string, unknown>) : {};
      }
      setDraft((prev) => [...prev, op]);
      setRedoStack([]);
      setNotice(`Staged ${op.op_type} for feature ${op.feature_id} in local draft.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid JSON payload.");
    }
  }

  function undoDraft(): void {
    if (draft.length === 0) return;
    const last = draft[draft.length - 1];
    if (!last) return;
    setDraft((prev) => prev.slice(0, -1));
    setRedoStack((prev) => [last, ...prev]);
  }

  function redoDraft(): void {
    if (redoStack.length === 0) return;
    const [first, ...rest] = redoStack;
    if (!first) return;
    setDraft((prev) => [...prev, first]);
    setRedoStack(rest);
  }

  async function saveChangeset(): Promise<void> {
    if (!activeSource || draft.length === 0) return;
    setError(null);
    setNotice(null);
    try {
      const csrf = await loadCsrfToken(apiClient);
      const cs = await commitChangeset(
        apiClient,
        organizationId,
        projectId,
        activeSource.id,
        {
          base_content_revision: activeSource.content_revision,
          operation_id: `ui-cs-${Date.now()}`,
          summary,
          operations: draft
        },
        csrf
      );
      setDraft([]);
      setRedoStack([]);
      setNotice(`Committed changeset ${cs.id} (rev ${cs.resulting_content_revision.slice(0, 12)}).`);
      await qc.invalidateQueries({ queryKey: ["r006", organizationId, projectId] });
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message} (Local draft preserved — refresh source to reapply.)`
          : "Commit failed; local draft preserved."
      );
    }
  }

  async function handleRevert(cs: Changeset): Promise<void> {
    setError(null);
    try {
      const csrf = await loadCsrfToken(apiClient);
      const rev = await revertChangeset(
        apiClient,
        organizationId,
        projectId,
        cs.id,
        `ui-rev-${Date.now()}`,
        csrf
      );
      setNotice(`Reverted changeset ${cs.id} via new changeset ${rev.id}.`);
      await qc.invalidateQueries({ queryKey: ["r006", organizationId, projectId] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Revert failed.");
    }
  }

  return (
    <div className="ovg-suite" data-testid="editing-workbench">
      <ProjectToolbar
        organizationId={organizationId}
        projectId={projectId}
        active="editing"
        title="R006 Editing & Change History"
      />
      <main className="ovg-suite-body">
        {notice && <div className="ovg-notice">{notice}</div>}
        {error && <div className="ovg-error">{error}</div>}

        <section className="ovg-card">
          <h2>Local Draft Session & Atomic Commit</h2>
          <div className="ovg-form-row">
            <label>
              Editable Source
              <select
                value={activeSource?.id ?? ""}
                onChange={(e) => setSelectedSourceId(e.target.value)}
              >
                {editableSources.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name} ({s.kind}, EPSG:{s.stored_crs?.code ?? 'N/A'})
                  </option>
                ))}
              </select>
            </label>
            <label>
              Operation
              <select
                value={opType}
                onChange={(e) => setOpType(e.target.value as "create" | "update" | "delete")}
              >
                <option value="create">Create Feature</option>
                <option value="update">Update Feature</option>
                <option value="delete">Delete Feature</option>
              </select>
            </label>
            <label>
              Feature ID
              <input value={featureId} onChange={(e) => setFeatureId(e.target.value)} />
            </label>
          </div>
          {opType !== "delete" && (
            <div className="ovg-form-row">
              <label style={{ flex: 1 }}>
                2D GeoJSON Geometry
                <input value={geomJson} onChange={(e) => setGeomJson(e.target.value)} />
              </label>
              <label style={{ flex: 1 }}>
                Typed Properties JSON
                <input value={propsJson} onChange={(e) => setPropsJson(e.target.value)} />
              </label>
            </div>
          )}
          <div className="ovg-form-row">
            <label style={{ flex: 1 }}>
              Changeset Summary
              <input value={summary} onChange={(e) => setSummary(e.target.value)} />
            </label>
            <button type="button" className="ovg-btn ovg-btn-secondary" onClick={stageOperation}>
              Stage to Draft
            </button>
            <button
              type="button"
              className="ovg-btn ovg-btn-secondary"
              onClick={undoDraft}
              disabled={draft.length === 0}
            >
              Undo ({draft.length})
            </button>
            <button
              type="button"
              className="ovg-btn ovg-btn-secondary"
              onClick={redoDraft}
              disabled={redoStack.length === 0}
            >
              Redo ({redoStack.length})
            </button>
            <button
              type="button"
              className="ovg-btn"
              onClick={() => void saveChangeset()}
              disabled={!activeSource || draft.length === 0}
            >
              Commit Changeset
            </button>
          </div>
        </section>

        <section className="ovg-card">
          <h2>Immutable Change History</h2>
          <table className="ovg-table">
            <thead>
              <tr>
                <th>Summary</th>
                <th>Actor</th>
                <th>Ops</th>
                <th>Result Revision</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {(historyQuery.data?.items ?? []).map((cs) => (
                <tr key={cs.id}>
                  <td>{cs.summary}</td>
                  <td>{cs.actor_display_snapshot}</td>
                  <td>{cs.operation_count}</td>
                  <td>
                    <code>{cs.resulting_content_revision.slice(0, 12)}</code>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="ovg-btn ovg-btn-secondary"
                      onClick={() => void handleRevert(cs)}
                    >
                      Revert
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}
