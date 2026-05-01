import { useEffect, useMemo, useState } from "react";
import FileUploader from "../components/FileUploader.jsx";
import IndexingProgress from "../components/IndexingProgress.jsx";
import { apiUpload, apiGet, apiPost } from "../utils/api.js";

export default function UploadPage() {
  const [pres, setPres] = useState(null);
  const [indexStatus, setIndexStatus] = useState(null);
  const [presentations, setPresentations] = useState([]);
  const [err, setErr] = useState("");
  const [uploading, setUploading] = useState(false);
  const [reindexingId, setReindexingId] = useState("");
  const [lastCheckedAt, setLastCheckedAt] = useState(null);

  const activePresentationId = useMemo(
    () => indexStatus?.presentation_id || pres?.presentation_id || "",
    [indexStatus?.presentation_id, pres?.presentation_id]
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await apiGet("/api/v1/presentations");
        if (!cancelled) setPresentations(Array.isArray(list) ? list : []);
      } catch {
        if (!cancelled) setPresentations([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!activePresentationId) return;
    let cancelled = false;
    let timer = null;

    const poll = async () => {
      try {
        const status = await apiGet(`/api/index-status/${activePresentationId}`);
        if (cancelled) return;
        setIndexStatus(status);
        setPres((prev) =>
          prev
            ? {
              ...prev,
              status: status.status,
              indexed_pages: status.indexed_pages,
              total_pages: status.total_pages,
            }
            : prev
        );
        setLastCheckedAt(Date.now());

        if (["uploaded", "indexing"].includes(String(status.status))) {
          timer = window.setTimeout(poll, 1500);
        }
      } catch {
        if (!cancelled) {
          timer = window.setTimeout(poll, 2500);
        }
      }
    };

    poll();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [activePresentationId]);

  function triggerIndexingRun(presentationId) {
    return apiPost(`/api/index-status/${presentationId}/run`, {}, { timeoutMs: 0 }).catch((error) => {
      setErr((prev) => prev || `Failed to start indexing: ${String(error?.message || error)}`);
    });
  }

  async function handleFile(file) {
    setErr("");
    setUploading(true);
    setPres(null);
    setIndexStatus(null);
    setLastCheckedAt(null);
    try {
      const p = await apiUpload(file);
      setPres(p);
      const list = await apiGet("/api/v1/presentations");
      setPresentations(Array.isArray(list) ? list : []);

      const uploadStatus = String(p?.status || "").toLowerCase();
      if (!["indexing", "ready"].includes(uploadStatus)) {
        // Trigger long-running indexing as a detached request.
        void triggerIndexingRun(p.presentation_id);
      }

      const status = await apiGet(`/api/index-status/${p.presentation_id}`);
      setIndexStatus(status);
      setLastCheckedAt(Date.now());
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setUploading(false);
    }
  }

  async function refresh() {
    if (!activePresentationId) return;
    try {
      const status = await apiGet(`/api/index-status/${activePresentationId}`);
      const list = await apiGet("/api/v1/presentations");
      setPresentations(Array.isArray(list) ? list : []);
      setIndexStatus(status);
      setPres((prev) =>
        prev
          ? {
            ...prev,
            status: status.status,
            indexed_pages: status.indexed_pages,
            total_pages: status.total_pages,
          }
          : prev
      );
      setLastCheckedAt(Date.now());
    } catch {
      /* ignore */
    }
  }

  async function runReindex(presentationId) {
    if (!presentationId) return;
    setReindexingId(presentationId);
    setErr("");
    try {
      void triggerIndexingRun(presentationId);

      const status = await apiGet(`/api/index-status/${presentationId}`);
      setIndexStatus(status);
      setPres((prev) =>
        prev && prev.presentation_id === presentationId
          ? {
            ...prev,
            status: status.status,
            indexed_pages: status.indexed_pages,
            total_pages: status.total_pages,
          }
          : prev
      );
      const list = await apiGet("/api/v1/presentations");
      setPresentations(Array.isArray(list) ? list : []);
      setLastCheckedAt(Date.now());
    } catch (e) {
      setErr(String(e.message || e));
    } finally {
      setReindexingId("");
    }
  }

  return (
    <section className="page-section">
      <header className="page-header reveal">
        <p className="eyebrow">Knowledge base</p>
        <h1>Presentations</h1>
        <p className="helper-text">
          Upload PDFs or PPTX decks, trigger indexing, and track retrieval readiness page-by-page.
          Every agent run is filtered to the selected presentation key.
        </p>
      </header>

      <div className="card stack-gap reveal">
        <FileUploader
          onUploaded={handleFile}
          busy={uploading}
        />
      </div>

      {err ? <div className="alert error">{err}</div> : null}

      <IndexingProgress
        presentation={pres}
        indexStatus={indexStatus}
        uploading={uploading}
        lastCheckedAt={lastCheckedAt}
      />

      {activePresentationId ? (
        <div className="button-row reveal">
          <button type="button" className="button button-secondary" onClick={refresh}>
            Refresh status
          </button>
        </div>
      ) : (
        <p className="helper-text">After upload, the presentation ID appears below for launch.</p>
      )}

      <div className="card stack-gap reveal">
        <div className="section-heading">
          <h2>Knowledge base catalog</h2>
          <p className="helper-text">Responsive catalog with status, chunk health, and filter keys.</p>
        </div>
        {!presentations.length ? (
          <p className="helper-text">No presentations indexed yet.</p>
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Presentation</th>
                  <th>Status</th>
                  <th>Pages</th>
                  <th>Document key</th>
                  <th>Slides indexed</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {presentations.map((item) => (
                  <tr key={item.presentation_id}>
                    <td>
                      <div className="cell-title">{item.filename}</div>
                      <div className="helper-text">
                        ID: <code>{item.presentation_id}</code>
                      </div>
                    </td>
                    <td>
                      <span className={`badge status-${item.status || "unknown"}`}>
                        {String(item.status || "unknown").replaceAll("_", " ")}
                      </span>
                      {item.index_error ? (
                        <div className="helper-text text-danger">Index error: {item.index_error}</div>
                      ) : null}
                    </td>
                    <td>
                      {item.indexed_pages}
                      {item.total_pages ? ` / ${item.total_pages}` : ""}
                    </td>
                    <td>{item.document_id ? <code>{item.document_id}</code> : "—"}</td>
                    <td>{typeof item.azure_indexed_chunks === "number" ? item.azure_indexed_chunks : "—"}</td>
                    <td>
                      <button
                        type="button"
                        className="button button-ghost button-sm"
                        disabled={reindexingId === item.presentation_id}
                        onClick={() => runReindex(item.presentation_id)}
                      >
                        {reindexingId === item.presentation_id ? "Re-indexing..." : "Re-index"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
