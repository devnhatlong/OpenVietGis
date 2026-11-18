import {
  listSpatialCatalogChanges,
  type SpatialCatalogChange
} from "@openvietgis/client-sdk";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { apiClient } from "../../app/api";
import { currentProtectedData, protectedQueryOptions } from "../../app/protected-query";
import {
  createHistoryTraversal, formatHistoryValue, HISTORY_PAGE_SIZE, historyKey,
  historyResponseMatchesScope, nextHistoryPage, previousHistoryPage, revisionEntries,
  type HistoryScope
} from "./catalog-history";

function RevisionDescription({ change, prior }: { change: SpatialCatalogChange; prior: boolean }) {
  const revision = prior ? change.prior_revision : change.new_revision;
  if (prior && revision === null) return <p>No prior revision (creation).</p>;
  const entries = revisionEntries(change.resource_type, revision);
  if (!entries.length) return <p>Revision unavailable.</p>;
  return (
    <dl style={{ overflowWrap: "anywhere" }}>
      {entries.map(([label, value]) => (
        <div key={label}><dt>{label}</dt><dd><code>{value}</code></dd></div>
      ))}
    </dl>
  );
}

function ChangeEvidence({ change }: { change: SpatialCatalogChange }) {
  return (
    <article aria-label={change.operation + " change"} style={{ borderTop: "1px solid #ccc", paddingTop: 12 }}>
      <h3>{change.operation}</h3>
      <dl style={{ overflowWrap: "anywhere" }}>
        <dt>Resource</dt><dd>{change.resource_type} · <code>{change.resource_id}</code></dd>
        <dt>Actor</dt><dd>{change.actor_display_snapshot} ({change.actor_type}) · <code>{change.actor_id}</code></dd>
        <dt>Recorded at (UTC)</dt><dd><time dateTime={change.created_at}>{change.created_at}</time></dd>
        <dt>Change ID</dt><dd><code>{change.id}</code></dd>
        <dt>Audit event ID</dt><dd><code>{change.audit_event_id}</code></dd>
      </dl>
      <h4>Prior revision</h4><RevisionDescription change={change} prior />
      <h4>New revision</h4><RevisionDescription change={change} prior={false} />
      <h4>Changed fields</h4>
      <div style={{ overflowX: "auto" }}>
        <table>
          <thead><tr><th>Field</th><th>Old value</th><th>New value</th></tr></thead>
          <tbody>{change.changes.map((value, index) => (
            <tr key={value.field + ":" + index}>
              <th scope="row">{value.field}</th>
              <td><code style={{ overflowWrap: "anywhere" }}>{formatHistoryValue(value.old_value)}</code></td>
              <td><code style={{ overflowWrap: "anywhere" }}>{formatHistoryValue(value.new_value)}</code></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </article>
  );
}

/** Mounted only behind the current account and exact active/archived Project gate. */
export function CatalogHistoryPanel({ scope }: { scope: HistoryScope }) {
  const [traversal, setTraversal] = useState(createHistoryTraversal);
  const query = useQuery({
    queryKey: historyKey(scope, traversal.cursor),
    queryFn: () => listSpatialCatalogChanges(apiClient, scope.organizationId, scope.projectId, {
      limit: HISTORY_PAGE_SIZE,
      ...(traversal.cursor === null ? {} : { after_id: traversal.cursor })
    }),
    ...protectedQueryOptions
  });
  const current = currentProtectedData(query);
  const mismatch = current !== undefined && !historyResponseMatchesScope(scope, current, traversal.cursor);
  const page = mismatch ? undefined : current;
  return (
    <section aria-label="Spatial change history" style={{ borderTop: "1px solid #aaa", marginTop: 32, paddingTop: 16 }}>
      <h2>Change history</h2>
      <p>Committed source and Layer changes, including retirement evidence. Ordered by change ID, not by time.
        Values are exact JSON scalars; null is distinct from empty text. Each page is a current-authority read.</p>
      {!page ? <>
        <p role={query.error || mismatch ? "alert" : "status"}>
          {mismatch ? "Change history does not match the current Project scope or continuation."
            : query.error ? "Unable to load current change history access." : "Checking current change history access…"}
        </p>
        {query.error || mismatch ? <>
          <button type="button" onClick={() => { void query.refetch(); }}>Retry history</button>{" "}
          <button type="button" disabled={!traversal.history.length}
            onClick={() => setTraversal(previousHistoryPage(traversal))}>Previous history</button>{" "}
          <button type="button" disabled={traversal.cursor === null}
            onClick={() => setTraversal(createHistoryTraversal())}>Reload from first page</button>
        </> : null}
      </> : <>
        {page.items.length === 0 ? <p>No recorded changes on this page.</p> :
          page.items.map(change => <ChangeEvidence key={change.id} change={change} />)}
        <p role="status">History page {traversal.history.length + 1} — {page.items.length} change(s).</p>
        <button type="button" disabled={!traversal.history.length}
          onClick={() => setTraversal(previousHistoryPage(traversal))}>Previous history</button>{" "}
        <button type="button" disabled={page.next_after_id === null}
          onClick={() => setTraversal(nextHistoryPage(traversal, page.next_after_id))}>Next history</button>{" "}
        <button type="button" onClick={() => {
          if (traversal.cursor === null) void query.refetch();
          else setTraversal(createHistoryTraversal());
        }}>Reload from first page</button>
      </>}
    </section>
  );
}
