function asNumber(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export default function IndexingProgress({
  presentation,
  indexStatus,
  uploading = false,
  lastCheckedAt = null,
}) {
  const info = indexStatus || presentation;
  if (!info && !uploading) return null;

  const presentationId = info?.presentation_id || presentation?.presentation_id || "pending";
  const status = uploading && !info ? "uploading" : String(info?.status || "unknown");
  const indexedPages = asNumber(info?.indexed_pages, 0);
  const totalPages = info?.total_pages == null ? null : asNumber(info.total_pages, 0);
  const indexError = info?.index_error || "";
  const documentId = info?.document_id || "";
  const azureIndexedChunks = info?.azure_indexed_chunks;

  const inProgress = ["uploading", "uploaded", "indexing"].includes(status);
  const hasPageTotals = totalPages != null && totalPages > 0;
  const progressPercent = hasPageTotals ? Math.min(100, Math.round((indexedPages / totalPages) * 100)) : null;

  return (
    <div className="card stack-gap reveal">
      <div className="section-heading">
        <h2>Indexing progress</h2>
        <p className="helper-text">Live ingestion and retrieval readiness status.</p>
      </div>

      <div className="inline-stack">
        <strong>{presentationId}</strong>
        <span className={`badge status-${status}`}>{status.replaceAll("_", " ")}</span>
      </div>

      {inProgress ? (
        <div className="loader-row">
          <span className="spinner" aria-hidden="true" />
          <span className="helper-text">Indexing in progress. This updates automatically.</span>
        </div>
      ) : null}

      <div className="progress-track" aria-hidden="true">
        <div
          className={`progress-fill ${inProgress && progressPercent == null ? "indeterminate" : ""}`}
          style={progressPercent != null ? { width: `${progressPercent}%` } : undefined}
        />
      </div>

      {hasPageTotals ? (
        <div className="helper-text">
          Indexed {indexedPages} / {totalPages} pages
          {progressPercent != null ? ` (${progressPercent}%)` : ""}
        </div>
      ) : null}

      {documentId ? (
        <div className="helper-text">
          Document filter key: <code>{documentId}</code>
        </div>
      ) : null}

      {typeof azureIndexedChunks === "number" ? (
        <div className="helper-text">Slides indexed to search: {azureIndexedChunks}</div>
      ) : null}

      {indexError ? (
        <div className="alert error">
          Indexing failed: {indexError}
          <br />
          Try uploading again or click refresh.
        </div>
      ) : null}

      {lastCheckedAt ? (
        <div className="helper-text">Last checked: {new Date(lastCheckedAt).toLocaleTimeString()}</div>
      ) : null}
    </div>
  );
}
