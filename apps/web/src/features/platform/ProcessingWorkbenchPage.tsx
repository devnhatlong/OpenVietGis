import {
  cancelProcessingJob,
  createProcessingJob,
  listProcessingAlgorithms,
  listProcessingJobs,
  listSpatialLayers,
  loadCsrfToken,
  retryProcessingJob
} from "@openvietgis/client-sdk";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { apiClient } from "../../app/api";
import { ProjectToolbar } from "./ProjectToolbar";

export function ProcessingWorkbenchPage() {
  const { organizationId = "", projectId = "" } = useParams();
  const qc = useQueryClient();
  const [algo, setAlgo] = useState<"buffer" | "clip" | "dissolve">("buffer");
  const [inputLayerId, setInputLayerId] = useState("");
  const [overlayLayerId, setOverlayLayerId] = useState("");
  const [distance, setDistance] = useState("500");
  const [groupField, setGroupField] = useState("");
  const [outputName, setOutputName] = useState("Derived Processing Layer");
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const layersQuery = useQuery({
    queryKey: ["r008", organizationId, projectId, "layers"],
    queryFn: () => listSpatialLayers(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });
  const algosQuery = useQuery({
    queryKey: ["r008", organizationId, projectId, "algos"],
    queryFn: () => listProcessingAlgorithms(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });
  const jobsQuery = useQuery({
    queryKey: ["r008", organizationId, projectId, "jobs"],
    queryFn: () => listProcessingJobs(apiClient, organizationId, projectId),
    enabled: Boolean(organizationId && projectId)
  });

  const layers = layersQuery.data?.items ?? [];
  const activeInput = inputLayerId || layers[0]?.id || "";

  async function runProcessing(): Promise<void> {
    if (!activeInput) return;
    setError(null);
    setNotice(null);
    try {
      const csrf = await loadCsrfToken(apiClient);
      const parameters =
        algo === "buffer"
          ? { distance_meters: Number(distance), quad_segs: 8 }
          : algo === "dissolve"
            ? { group_by_field: groupField.trim() || null }
            : {};
      const job = await createProcessingJob(
        apiClient,
        organizationId,
        projectId,
        {
          algorithm_id: algo,
          input_layer_id: activeInput,
          overlay_layer_id: algo === "clip" ? overlayLayerId || null : null,
          parameters,
          output_name: outputName,
          operation_id: `ui-proc-${Date.now()}`
        },
        csrf
      );
      setNotice(`Job ${job.id} completed (${job.status}, ${job.feature_count ?? 0} features).`);
      await qc.invalidateQueries({ queryKey: ["r008", organizationId, projectId] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed.");
    }
  }

  return (
    <div className="ovg-suite" data-testid="processing-workbench">
      <ProjectToolbar
        organizationId={organizationId}
        projectId={projectId}
        active="processing"
        title="R008 Spatial Processing & Durable Jobs"
      />
      <main className="ovg-suite-body">
        {notice && <div className="ovg-notice">{notice}</div>}
        {error && <div className="ovg-error">{error}</div>}
        <section className="ovg-card">
          <h2>Run Registered Spatial Algorithm ({algosQuery.data?.items.length ?? 3})</h2>
          <div className="ovg-form-row">
            <label>
              Algorithm
              <select
                value={algo}
                onChange={(e) => setAlgo(e.target.value as "buffer" | "clip" | "dissolve")}
              >
                <option value="buffer">Buffer</option>
                <option value="clip">Clip</option>
                <option value="dissolve">Dissolve</option>
              </select>
            </label>
            <label>
              Input Layer
              <select value={activeInput} onChange={(e) => setInputLayerId(e.target.value)}>
                {layers.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
            </label>
            {algo === "clip" && (
              <label>
                Overlay Layer
                <select value={overlayLayerId} onChange={(e) => setOverlayLayerId(e.target.value)}>
                  <option value="">Select overlay</option>
                  {layers.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {algo === "buffer" && (
              <label>
                Distance (m)
                <input value={distance} onChange={(e) => setDistance(e.target.value)} />
              </label>
            )}
            {algo === "dissolve" && (
              <label>
                Group Field (optional)
                <input value={groupField} onChange={(e) => setGroupField(e.target.value)} />
              </label>
            )}
            <label>
              New Output Layer Name
              <input value={outputName} onChange={(e) => setOutputName(e.target.value)} />
            </label>
            <button type="button" className="ovg-btn" disabled={!activeInput} onClick={() => void runProcessing()}>
              Run Job
            </button>
          </div>
        </section>

        <section className="ovg-card">
          <h2>Processing Jobs History</h2>
          <table className="ovg-table">
            <thead>
              <tr>
                <th>Algorithm</th>
                <th>Output Layer</th>
                <th>Status</th>
                <th>Features</th>
                <th>Engine</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {(jobsQuery.data?.items ?? []).map((j) => (
                <tr key={j.id}>
                  <td>{j.algorithm_id}</td>
                  <td>{j.output_name}</td>
                  <td>
                    <span className="ovg-badge">{j.status}</span>
                  </td>
                  <td>{j.feature_count ?? "—"}</td>
                  <td>{j.engine_version}</td>
                  <td>
                    {j.status === "queued" && (
                      <button
                        type="button"
                        className="ovg-btn ovg-btn-secondary"
                        onClick={async () => {
                          const csrf = await loadCsrfToken(apiClient);
                          await cancelProcessingJob(apiClient, organizationId, projectId, j.id, csrf);
                          await qc.invalidateQueries({ queryKey: ["r008", organizationId, projectId, "jobs"] });
                        }}
                      >
                        Cancel
                      </button>
                    )}
                    {(j.status === "failed" || j.status === "cancelled") && (
                      <button
                        type="button"
                        className="ovg-btn ovg-btn-secondary"
                        onClick={async () => {
                          const csrf = await loadCsrfToken(apiClient);
                          await retryProcessingJob(apiClient, organizationId, projectId, j.id, csrf);
                          await qc.invalidateQueries({ queryKey: ["r008", organizationId, projectId, "jobs"] });
                        }}
                      >
                        Retry
                      </button>
                    )}
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
