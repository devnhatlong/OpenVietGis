import {
  TransferApiError,
  artifactDownloadUrl,
  cancelTransferJob,
  confirmExport,
  confirmImport,
  getEffectivePermissions,
  getProject,
  inspectImportAsset,
  listSpatialLayers,
  listTransferJobs,
  loadCsrfToken,
  previewExport,
  retryTransferJob,
  uploadImportAsset,
  type ExportPreviewResponse,
  type ImportInspectionResponse,
  type Project,
  type SpatialLayer,
  type TransferFormat
} from "@openvietgis/client-sdk";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiClient } from "../../app/api";
import { currentProtectedData, protectedQueryOptions } from "../../app/protected-query";
import { FreshAccount } from "../auth/FreshAccount";
import "./transfers.css";

const CRS_OPTIONS = [
  { code: 4326, label: "EPSG:4326 — WGS 84" },
  { code: 3857, label: "EPSG:3857 — Web Mercator" },
  { code: 4756, label: "EPSG:4756 — VN-2000 Geographic" },
  { code: 5899, label: "EPSG:5899 — VN-2000 TM-3 107-45" }
];

const ENCODING_OPTIONS = ["utf-8", "windows-1258", "cp1252", "latin-1"];

function errText(err: unknown): string {
  if (err instanceof TransferApiError) return `${err.code}: ${err.detail}`;
  if (err instanceof Error) return err.message;
  return "Transfer operation failed.";
}

function TransfersWorkspace({
  organizationId,
  projectId,
  accountId,
  project,
  canEdit
}: {
  organizationId: string;
  projectId: string;
  accountId: string;
  project: Project;
  canEdit: boolean;
}) {
  const queryClient = useQueryClient();
  const writable = canEdit && project.status === "active";
  const scopePrefix = ["transfers", accountId, organizationId, projectId];

  const layersQuery = useQuery({
    queryKey: [...scopePrefix, "layers"],
    queryFn: () => listSpatialLayers(apiClient, organizationId, projectId, { limit: 100 }),
    ...protectedQueryOptions
  });
  const jobsQuery = useQuery({
    queryKey: [...scopePrefix, "jobs"],
    queryFn: () => listTransferJobs(apiClient, organizationId, projectId, 50),
    ...protectedQueryOptions
  });

  const layers = currentProtectedData(layersQuery)?.items ?? [];
  const jobs = currentProtectedData(jobsQuery)?.items ?? [];

  // Import state
  const [inspection, setInspection] = useState<ImportInspectionResponse | null>(null);
  const [selectedMember, setSelectedMember] = useState("");
  const [declaredCrs, setDeclaredCrs] = useState<string>("");
  const [targetCrs, setTargetCrs] = useState<string>("");
  const [declaredEncoding, setDeclaredEncoding] = useState<string>("");
  const [sourceName, setSourceName] = useState("");
  const [layerName, setLayerName] = useState("");
  const [approvedImportConversions, setApprovedImportConversions] = useState<string[]>([]);
  const [importNotice, setImportNotice] = useState("");
  const [importBusy, setImportBusy] = useState(false);

  // Export state
  const [exportLayerId, setExportLayerId] = useState("");
  const [exportFormat, setExportFormat] = useState<TransferFormat>("geopackage");
  const [exportCrs, setExportCrs] = useState<number>(4326);
  const [exportPreview, setExportPreview] = useState<ExportPreviewResponse | null>(null);
  const [approvedDisclosures, setApprovedDisclosures] = useState<string[]>([]);
  const [exportNotice, setExportNotice] = useState("");
  const [exportBusy, setExportBusy] = useState(false);

  const exportableLayers = layers.filter(l =>
    l.capabilities.some(c => c.name === "export" && c.available && c.actor_authorized)
  );
  const activeExportLayer: SpatialLayer | undefined = exportableLayers.find(
    l => l.id === exportLayerId
  );

  async function handleUpload(file: File): Promise<void> {
    if (!writable || importBusy) return;
    setImportBusy(true);
    setImportNotice("");
    try {
      await loadCsrfToken(apiClient);
      const res = await uploadImportAsset(apiClient, organizationId, projectId, file, file.name);
      setInspection(res);
      setSelectedMember(res.inspection.selected_member ?? "");
      setDeclaredCrs(
        res.inspection.resolved_source_crs ? String(res.inspection.resolved_source_crs) : ""
      );
      setTargetCrs(res.inspection.target_crs ? String(res.inspection.target_crs) : "");
      setDeclaredEncoding(res.inspection.resolved_encoding ?? "");
      const stem = file.name.replace(/\.[^.]+$/, "");
      setSourceName(stem || "Imported Source");
      setLayerName(stem || "Imported Layer");
      setApprovedImportConversions([]);
      setImportNotice(`Uploaded ${res.asset.filename} (${res.asset.detected_format}).`);
    } catch (err) {
      setImportNotice(errText(err));
    } finally {
      setImportBusy(false);
    }
  }

  async function handleReinspect(): Promise<void> {
    if (!inspection || !writable || importBusy) return;
    setImportBusy(true);
    setImportNotice("");
    try {
      await loadCsrfToken(apiClient);
      const res = await inspectImportAsset(apiClient, organizationId, projectId, {
        source_asset_id: inspection.asset.id,
        selected_member: selectedMember || null,
        declared_source_crs: declaredCrs ? Number(declaredCrs) : null,
        target_crs: targetCrs ? Number(targetCrs) : null,
        declared_encoding: declaredEncoding || null
      });
      setInspection(res);
      setImportNotice(
        res.inspection.confirmable
          ? "Inspection passed. Ready to confirm import."
          : "Inspection completed with issues to resolve."
      );
    } catch (err) {
      setImportNotice(errText(err));
    } finally {
      setImportBusy(false);
    }
  }

  async function handleConfirmImport(): Promise<void> {
    if (!inspection || !inspection.inspection.selected_member || !writable || importBusy) return;
    setImportBusy(true);
    setImportNotice("");
    try {
      await loadCsrfToken(apiClient);
      const job = await confirmImport(apiClient, organizationId, projectId, {
        operation_id: crypto.randomUUID(),
        source_asset_id: inspection.asset.id,
        selected_member: inspection.inspection.selected_member,
        source_name: sourceName.trim(),
        layer_name: layerName.trim(),
        declared_source_crs: declaredCrs ? Number(declaredCrs) : null,
        target_crs: targetCrs ? Number(targetCrs) : null,
        declared_encoding: declaredEncoding || null,
        approved_conversions: approvedImportConversions,
        inspection_fingerprint: inspection.inspection.inspection_fingerprint
      });
      setImportNotice(
        `Import succeeded: Layer ${job.target_layer_id} (${job.result_report?.feature_count ?? 0} features).`
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: [...scopePrefix, "layers"] }),
        queryClient.invalidateQueries({ queryKey: [...scopePrefix, "jobs"] })
      ]);
    } catch (err) {
      setImportNotice(errText(err));
    } finally {
      setImportBusy(false);
    }
  }

  async function handlePreviewExport(): Promise<void> {
    if (!activeExportLayer || exportBusy) return;
    setExportBusy(true);
    setExportNotice("");
    setExportPreview(null);
    setApprovedDisclosures([]);
    try {
      await loadCsrfToken(apiClient);
      const preview = await previewExport(apiClient, organizationId, projectId, {
        layer_id: activeExportLayer.id,
        content_revision: activeExportLayer.source.content_revision,
        schema_revision: activeExportLayer.source.schema_revision,
        output_format: exportFormat,
        output_crs: exportCrs
      });
      setExportPreview(preview);
      setExportNotice("Export preview ready for pinned revision.");
    } catch (err) {
      setExportNotice(errText(err));
    } finally {
      setExportBusy(false);
    }
  }

  async function handleConfirmExport(): Promise<void> {
    if (!exportPreview || exportBusy) return;
    setExportBusy(true);
    setExportNotice("");
    try {
      await loadCsrfToken(apiClient);
      const job = await confirmExport(apiClient, organizationId, projectId, {
        operation_id: crypto.randomUUID(),
        layer_id: exportPreview.layer_id,
        content_revision: exportPreview.content_revision,
        schema_revision: exportPreview.schema_revision,
        output_format: exportPreview.output_format,
        output_crs: exportPreview.output_crs,
        approved_disclosures: approvedDisclosures,
        preview_fingerprint: exportPreview.preview_fingerprint
      });
      setExportNotice(
        `Export succeeded: ${job.artifact?.filename ?? "artifact ready"} (SHA-256 ${job.artifact?.sha256.slice(0, 12)}…).`
      );
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: [...scopePrefix, "layers"] }),
        queryClient.invalidateQueries({ queryKey: [...scopePrefix, "jobs"] })
      ]);
    } catch (err) {
      setExportNotice(errText(err));
    } finally {
      setExportBusy(false);
    }
  }

  async function handleJobAction(jobId: string, action: "cancel" | "retry"): Promise<void> {
    await loadCsrfToken(apiClient);
    if (action === "cancel") await cancelTransferJob(apiClient, organizationId, projectId, jobId);
    else await retryTransferJob(apiClient, organizationId, projectId, jobId);
    await Promise.all([
        queryClient.invalidateQueries({ queryKey: [...scopePrefix, "layers"] }),
        queryClient.invalidateQueries({ queryKey: [...scopePrefix, "jobs"] })
      ]);
  }

  const requiredExportApprovals =
    exportPreview?.disclosures.filter(d => d.requires_approval).map(d => d.code) ?? [];
  const exportApprovalsMet = requiredExportApprovals.every(code =>
    approvedDisclosures.includes(code)
  );

  return (
    <main className="transfers-page" data-testid="transfers-page">
      <header className="transfers-header">
        <div>
          <Link to={`/organizations/${organizationId}/projects`}>← Projects</Link>
          <h1>
            {project.name} <small>Import &amp; Export</small>
          </h1>
        </div>
        <nav className="transfers-nav">
          <Link to={`/organizations/${organizationId}/projects/${projectId}/spatial`}>
            Spatial catalog
          </Link>
          <Link to={`/organizations/${organizationId}/projects/${projectId}/map`}>
            Map workspace
          </Link>
        </nav>
      </header>

      <div className="transfers-grid">
        <section className="transfers-card" aria-label="Import vector dataset">
          <h2>Import Vector Layer</h2>
          {!writable ? (
            <p className="transfers-muted">
              Read-only access: importing new sources requires Project edit authority on an active
              Project.
            </p>
          ) : (
            <>
              <label className="transfers-field">
                <span>Dataset file (.gpkg, .geojson, .zip Shapefile)</span>
                <input
                  type="file"
                  data-testid="import-file-input"
                  accept=".gpkg,.geojson,.json,.zip"
                  disabled={importBusy}
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) void handleUpload(file);
                  }}
                />
              </label>

              {inspection ? (
                <div className="transfers-inspection" data-testid="import-inspection">
                  <p>
                    <strong>Format:</strong> {inspection.asset.detected_format} ·{" "}
                    <strong>SHA-256:</strong>{" "}
                    <code>{inspection.asset.sha256.slice(0, 16)}…</code>
                  </p>
                  <div className="transfers-form-row">
                    <label>
                      <span>Member</span>
                      <select
                        data-testid="import-member-select"
                        value={selectedMember}
                        onChange={e => setSelectedMember(e.target.value)}
                      >
                        <option value="">Choose member…</option>
                        {inspection.inspection.members.map(m => (
                          <option key={m.name} value={m.name} disabled={!m.eligible}>
                            {m.name} ({m.geometry_family}, {m.feature_count} features
                            {m.eligible ? "" : ` — ${m.reason}`})
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Source CRS</span>
                      <select
                        data-testid="import-source-crs"
                        value={declaredCrs}
                        onChange={e => setDeclaredCrs(e.target.value)}
                      >
                        <option value="">Auto / File CRS</option>
                        {CRS_OPTIONS.map(o => (
                          <option key={o.code} value={String(o.code)}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Target CRS</span>
                      <select
                        data-testid="import-target-crs"
                        value={targetCrs}
                        onChange={e => setTargetCrs(e.target.value)}
                      >
                        <option value="">Keep source CRS</option>
                        {CRS_OPTIONS.map(o => (
                          <option key={o.code} value={String(o.code)}>
                            {o.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Text Encoding</span>
                      <select
                        data-testid="import-encoding"
                        value={declaredEncoding}
                        onChange={e => setDeclaredEncoding(e.target.value)}
                      >
                        <option value="">Auto (.cpg / UTF-8)</option>
                        {ENCODING_OPTIONS.map(enc => (
                          <option key={enc} value={enc}>
                            {enc}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <button
                    type="button"
                    disabled={importBusy}
                    onClick={() => void handleReinspect()}
                  >
                    Re-inspect
                  </button>

                  {inspection.inspection.findings.length > 0 ? (
                    <ul className="transfers-findings" data-testid="import-findings">
                      {inspection.inspection.findings.map((f, i) => (
                        <li key={i} className={`finding-${f.severity}`}>
                          <strong>[{f.code}]</strong> {f.message}
                        </li>
                      ))}
                    </ul>
                  ) : null}

                  <div className="transfers-form-row">
                    <label>
                      <span>New Source Name</span>
                      <input
                        type="text"
                        data-testid="import-source-name"
                        value={sourceName}
                        onChange={e => setSourceName(e.target.value)}
                      />
                    </label>
                    <label>
                      <span>New Layer Name</span>
                      <input
                        type="text"
                        data-testid="import-layer-name"
                        value={layerName}
                        onChange={e => setLayerName(e.target.value)}
                      />
                    </label>
                  </div>

                  <button
                    type="button"
                    className="transfers-primary"
                    data-testid="confirm-import-btn"
                    disabled={
                      importBusy ||
                      !inspection.inspection.confirmable ||
                      !sourceName.trim() ||
                      !layerName.trim()
                    }
                    onClick={() => void handleConfirmImport()}
                  >
                    Confirm Import ({inspection.inspection.feature_count} features)
                  </button>
                </div>
              ) : null}
            </>
          )}
          {importNotice ? (
            <p className="transfers-notice" role="status" data-testid="import-notice">
              {importNotice}
            </p>
          ) : null}
        </section>

        <section className="transfers-card" aria-label="Export fixed revision">
          <h2>Export Fixed Revision</h2>
          <div className="transfers-form-row">
            <label>
              <span>Layer</span>
              <select
                data-testid="export-layer-select"
                value={exportLayerId}
                onChange={e => {
                  setExportLayerId(e.target.value);
                  setExportPreview(null);
                  const chosen = exportableLayers.find(l => l.id === e.target.value);
                  if (chosen?.source.stored_crs?.code) setExportCrs(chosen.source.stored_crs.code);
                }}
              >
                <option value="">Choose exportable Layer…</option>
                {exportableLayers.map(l => (
                  <option key={l.id} value={l.id}>
                    {l.name} ({l.source.feature_count ?? 0} features, EPSG:
                    {l.source.stored_crs?.code ?? "?"})
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Output Format</span>
              <select
                data-testid="export-format-select"
                value={exportFormat}
                onChange={e => {
                  const fmt = e.target.value as TransferFormat;
                  setExportFormat(fmt);
                  if (fmt === "geojson") setExportCrs(4326);
                  setExportPreview(null);
                }}
              >
                <option value="geopackage">GeoPackage (.gpkg — preferred lossless)</option>
                <option value="geojson">RFC 7946 GeoJSON (.geojson — EPSG:4326)</option>
                <option value="shapefile_zip">ZIP Shapefile (.zip)</option>
              </select>
            </label>
            <label>
              <span>Output CRS</span>
              <select
                data-testid="export-crs-select"
                value={exportCrs}
                onChange={e => {
                  setExportCrs(Number(e.target.value));
                  setExportPreview(null);
                }}
              >
                {CRS_OPTIONS.map(o => (
                  <option
                    key={o.code}
                    value={o.code}
                    disabled={exportFormat === "geojson" && o.code !== 4326}
                  >
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <button
            type="button"
            data-testid="preview-export-btn"
            disabled={!activeExportLayer || exportBusy}
            onClick={() => void handlePreviewExport()}
          >
            Preview Export
          </button>

          {exportPreview ? (
            <div className="transfers-inspection" data-testid="export-preview">
              <p>
                <strong>Pinned Content Revision:</strong>{" "}
                <code>{exportPreview.content_revision.slice(0, 16)}…</code> ·{" "}
                <strong>Features:</strong> {exportPreview.feature_count}
              </p>
              {exportPreview.disclosures.length > 0 ? (
                <ul className="transfers-findings">
                  {exportPreview.disclosures.map(d => (
                    <li key={d.code}>
                      <strong>[{d.code}]</strong> {d.message}
                      {d.requires_approval ? (
                        <label className="transfers-approval">
                          <input
                            type="checkbox"
                            checked={approvedDisclosures.includes(d.code)}
                            onChange={e => {
                              setApprovedDisclosures(prev =>
                                e.target.checked
                                  ? [...prev, d.code]
                                  : prev.filter(item => item !== d.code)
                              );
                            }}
                          />
                          Approve this representational difference
                        </label>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="transfers-muted">Lossless profile: no representational loss.</p>
              )}
              <button
                type="button"
                className="transfers-primary"
                data-testid="confirm-export-btn"
                disabled={exportBusy || !exportApprovalsMet}
                onClick={() => void handleConfirmExport()}
              >
                Confirm Export
              </button>
            </div>
          ) : null}
          {exportNotice ? (
            <p className="transfers-notice" role="status" data-testid="export-notice">
              {exportNotice}
            </p>
          ) : null}
        </section>
      </div>

      <section className="transfers-card" aria-label="Lịch sử tác vụ Nhập / Xuất">
        <h2>Durable Import &amp; Export Jobs</h2>
        {jobs.length === 0 ? (
          <p className="transfers-muted">No transfer jobs recorded in this Project yet.</p>
        ) : (
          <table className="transfers-table" data-testid="transfer-jobs-table">
            <thead>
              <tr>
                <th>Kind</th>
                <th>Status</th>
                <th>Actor</th>
                <th>Revision / Provenance</th>
                <th>Output / Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map(job => (
                <tr key={job.id} data-testid={`job-row-${job.id}`}>
                  <td>{job.kind}</td>
                  <td>
                    <span className={`job-badge job-${job.status}`}>{job.status}</span>
                  </td>
                  <td>{job.actor_display_snapshot}</td>
                  <td>
                    {job.source_content_revision ? (
                      <code>{job.source_content_revision.slice(0, 14)}…</code>
                    ) : (
                      "—"
                    )}
                    {job.error_message ? <div className="job-error">{job.error_message}</div> : null}
                  </td>
                  <td>
                    {job.artifact ? (
                      <div className="artifact-cell">
                        <a
                          data-testid={`download-artifact-${job.artifact.id}`}
                          href={artifactDownloadUrl(organizationId, projectId, job.artifact.id)}
                          download={job.artifact.filename}
                        >
                          Download {job.artifact.filename}
                        </a>
                        <small>
                          SHA-256 <code>{job.artifact.sha256.slice(0, 12)}…</code> ·{" "}
                          {job.artifact.output_format} · EPSG:{job.artifact.output_crs}
                        </small>
                      </div>
                    ) : job.target_layer_id ? (
                      <Link to={`/organizations/${organizationId}/projects/${projectId}/map`}>
                        Open in Map
                      </Link>
                    ) : null}
                    {job.status === "recoverable_failed" ? (
                      <button type="button" onClick={() => void handleJobAction(job.id, "retry")}>
                        Retry
                      </button>
                    ) : null}
                    {job.status === "queued" || job.status === "active" ? (
                      <button type="button" onClick={() => void handleJobAction(job.id, "cancel")}>
                        Cancel
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  );
}

function ProtectedTransfers({
  organizationId,
  projectId,
  accountId
}: {
  organizationId: string;
  projectId: string;
  accountId: string;
}) {
  const prefix = ["transfers", accountId, organizationId, projectId];
  const projectQuery = useQuery({
    queryKey: [...prefix, "project"],
    queryFn: () => getProject(apiClient, organizationId, projectId),
    ...protectedQueryOptions
  });
  const permissionQuery = useQuery({
    queryKey: [...prefix, "permissions"],
    queryFn: () => getEffectivePermissions(apiClient, organizationId, { project_id: projectId }),
    ...protectedQueryOptions
  });
  const project = currentProtectedData(projectQuery);
  const permissions = currentProtectedData(permissionQuery);
  if (
    !project ||
    !permissions ||
    project.id !== projectId ||
    project.organization_id !== organizationId ||
    project.status === "deleted" ||
    !permissions.permissions.includes("project.read")
  ) {
    const error = projectQuery.error || permissionQuery.error;
    return (
      <main className="transfers-page">
        <Link to={`/organizations/${organizationId}/projects`}>← Projects</Link>
        <h1>Import &amp; Export</h1>
        <p role={error ? "alert" : "status"}>
          {error
            ? "Current Project transfer access is unavailable."
            : "Checking current Project transfer access…"}
        </p>
      </main>
    );
  }
  return (
    <TransfersWorkspace
      key={`${accountId}:${organizationId}:${projectId}`}
      organizationId={organizationId}
      projectId={projectId}
      accountId={accountId}
      project={project}
      canEdit={permissions.permissions.includes("project.edit")}
    />
  );
}

export function ImportExportPage() {
  const { organizationId, projectId } = useParams();
  if (!organizationId || !projectId) {
    return <p role="alert">Project context is missing.</p>;
  }
  return (
    <FreshAccount key={`${organizationId}:${projectId}`}>
      {account => (
        <ProtectedTransfers
          key={`${account.id}:${organizationId}:${projectId}`}
          accountId={account.id}
          organizationId={organizationId}
          projectId={projectId}
        />
      )}
    </FreshAccount>
  );
}
