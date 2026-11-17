import {
  ApiClient,
  createFoundationRecord,
  getFoundationRecord,
  getReadiness,
  type FoundationRecord,
  type ReadyResponse
} from "@openvietgis/client-sdk";
import { FormEvent, useEffect, useMemo, useState } from "react";

function describeReadiness(value: ReadyResponse | null): string {
  if (value === null) {
    return "Checking foundation readiness…";
  }
  return value.status === "ready"
    ? "Foundation ready — database connected"
    : "Foundation not ready — database unavailable";
}

export function FoundationPage() {
  const client = useMemo(
    () =>
      new ApiClient({
        baseUrl: import.meta.env.VITE_OPENVIETGIS_API_BASE_URL ?? "/api/v1"
      }),
    []
  );
  const [readiness, setReadiness] = useState<ReadyResponse | null>(null);
  const [label, setLabel] = useState("");
  const [lookupId, setLookupId] = useState("");
  const [record, setRecord] = useState<FoundationRecord | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getReadiness(client)
      .then(setReadiness)
      .catch(() => setReadiness({ status: "not_ready", database: "unavailable" }));
  }, [client]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const created = await createFoundationRecord(client, { label });
      setRecord(created);
      setLookupId(created.id);
      setLabel("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Create failed");
    }
  }

  async function handleLookup(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      setRecord(await getFoundationRecord(client, lookupId));
    } catch (caught) {
      setRecord(null);
      setError(caught instanceof Error ? caught.message : "Lookup failed");
    }
  }

  return (
    <main style={{ maxWidth: 760, margin: "48px auto", fontFamily: "system-ui, sans-serif" }}>
      <header>
        <p style={{ textTransform: "uppercase", letterSpacing: "0.12em" }}>OpenVietGIS</p>
        <h1>Platform foundation</h1>
        <p data-testid="readiness">{describeReadiness(readiness)}</p>
      </header>

      <section aria-labelledby="foundation-record-title">
        <h2 id="foundation-record-title">Foundation sample record</h2>
        <p>
          Disposable non-GIS data used only to prove the web → API → application → persistence
          path.
        </p>

        <form onSubmit={handleCreate}>
          <label>
            Label
            <input
              aria-label="Foundation record label"
              value={label}
              maxLength={120}
              onChange={(event) => setLabel(event.target.value)}
            />
          </label>
          <button type="submit">Create record</button>
        </form>

        <form onSubmit={handleLookup}>
          <label>
            Record UUID
            <input
              aria-label="Foundation record UUID"
              value={lookupId}
              onChange={(event) => setLookupId(event.target.value)}
            />
          </label>
          <button type="submit">Load record</button>
        </form>

        {error ? <p role="alert">{error}</p> : null}

        {record ? (
          <dl data-testid="foundation-record">
            <dt>ID</dt>
            <dd>{record.id}</dd>
            <dt>Label</dt>
            <dd>{record.label}</dd>
          </dl>
        ) : null}
      </section>
    </main>
  );
}
