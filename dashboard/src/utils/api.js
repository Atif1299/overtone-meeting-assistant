const base = () => (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const API_TIMEOUT_MS = 12000;
const API_UPLOAD_TIMEOUT_MS = 45000;
const SINGLE_UPLOAD_LIMIT_BYTES = 4 * 1024 * 1024;
const CHUNK_SIZE_BYTES = 3 * 1024 * 1024;
const ADMIN_API_KEY = import.meta.env.VITE_ADMIN_API_KEY || "";
// 
const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";
const ADMIN_KEY = import.meta.env.VITE_ADMIN_API_KEY || "";
const ADMIN_TOKEN_STORAGE_KEY = "admin_token";

function getAuthToken() {
  return sessionStorage.getItem(ADMIN_TOKEN_STORAGE_KEY) || "";
}

export function hasAdminSession() {
  return Boolean(getAuthToken());
}

export function setAdminSession(adminKey) {
  sessionStorage.setItem(ADMIN_TOKEN_STORAGE_KEY, adminKey);
}

export function clearAdminSession() {
  sessionStorage.removeItem(ADMIN_TOKEN_STORAGE_KEY);
}

async function apiFetch(endpoint, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "x-api-key": ADMIN_KEY,
    Authorization: `Bearer ${getAuthToken()}`,
    ...(options.headers || {})
  };

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers
  });

  if (!res.ok) {
    const err = await res.text();
    const requestError = new Error(err || "Request failed");
    requestError.status = res.status;
    throw requestError;
  }

  return res.json();
}

export async function verifyAdminApiKey(adminApiKey) {
  const response = await fetch(`${API_BASE}/auth/admin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ admin_api_key: adminApiKey }),
  });

  if (!response.ok) {
    const text = await response.text();
    const requestError = new Error(text || "Admin authentication failed");
    requestError.status = response.status;
    throw requestError;
  }

  return response.json();
}

export async function createCustomer(customer_name) {
  return apiFetch("/api/admin/customer", {
    method: "POST",
    body: JSON.stringify({ customer_name })
  });
}

export async function listCustomers() {
  return apiFetch("/api/admin/customer");
}
// 



function withAdminHeader(headers = {}) {
  if (!ADMIN_API_KEY) return headers;
  return { ...headers, "X-API-Key": ADMIN_API_KEY };
}

async function parseError(response) {
  const text = await response.text();
  if (!text) return `Request failed (${response.status})`;
  try {
    const data = JSON.parse(text);
    if (typeof data?.detail === "string") return data.detail;
    return text;
  } catch {
    return text;
  }
}

async function request(path, init = {}, timeoutMs = API_TIMEOUT_MS) {
  const useTimeout = Number.isFinite(timeoutMs) && timeoutMs > 0;
  const controller = useTimeout ? new AbortController() : null;
  const timeout = useTimeout ? setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    const response = await fetch(`${base()}${path}`, {
      ...init,
      headers: withAdminHeader(init.headers || {}),
      signal: controller?.signal,
    });
    if (!response.ok) throw new Error(await parseError(response));
    return response;
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("Request timed out. Confirm backend is reachable.");
    }
    throw error;
  } finally {
    if (timeout) clearTimeout(timeout);
  }
}

export async function apiGet(path) {
  const response = await request(path);
  return response.json();
}

export async function apiPost(path, body, options = {}) {
  const response = await request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }, options.timeoutMs ?? API_TIMEOUT_MS);
  return response.json();
}

export async function apiUpload(file) {
  try {
    return await apiDirectBlobUpload(file);
  } catch (error) {
    const message = String(error?.message || error);
    if (!message.toLowerCase().includes("direct upload")) {
      throw error;
    }
  }

  if (file.size > SINGLE_UPLOAD_LIMIT_BYTES) {
    return apiChunkedUpload(file);
  }

  const fd = new FormData();
  fd.append("file", file);
  const response = await request("/api/v1/presentations", { method: "POST", body: fd }, API_UPLOAD_TIMEOUT_MS);
  return response.json();
}

async function apiDirectBlobUpload(file) {
  const initForm = new FormData();
  initForm.append("filename", file.name);
  initForm.append("total_size", String(file.size));

  let initPayload;
  try {
    const initResponse = await request(
      "/api/v1/presentations/direct/init",
      { method: "POST", body: initForm },
      API_UPLOAD_TIMEOUT_MS
    );
    initPayload = await initResponse.json();
  } catch (error) {
    const message = String(error?.message || error);
    if (message.includes("404") || message.toLowerCase().includes("not found")) {
      throw new Error("direct upload endpoint unavailable");
    }
    throw new Error(`direct upload init failed: ${message}`);
  }

  const uploadUrl = initPayload?.upload_url;
  const presentationId = initPayload?.presentation?.presentation_id;
  if (!uploadUrl || !presentationId) {
    throw new Error("direct upload init response is missing upload_url or presentation id");
  }

  const blobResponse = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      "x-ms-blob-type": "BlockBlob",
      "Content-Type": file.type || "application/octet-stream",
    },
    body: file,
  });
  if (!blobResponse.ok) {
    throw new Error(`direct upload to blob failed (${blobResponse.status})`);
  }

  const completed = await apiPost("/api/v1/presentations/direct/complete", {
    presentation_id: presentationId,
  });
  return completed;
}

async function apiChunkedUpload(file) {
  const totalChunks = Math.max(1, Math.ceil(file.size / CHUNK_SIZE_BYTES));

  const initForm = new FormData();
  initForm.append("filename", file.name);
  initForm.append("total_size", String(file.size));
  initForm.append("total_chunks", String(totalChunks));
  let initPayload;
  try {
    const initResponse = await request(
      "/api/v1/presentations/init",
      { method: "POST", body: initForm },
      API_UPLOAD_TIMEOUT_MS
    );
    initPayload = await initResponse.json();
  } catch (error) {
    const message = String(error?.message || error);
    if (message.includes("404") || message.toLowerCase().includes("not found")) {
      throw new Error(
        "Large-file upload endpoint is unavailable on the deployed backend. Upload files under 4 MB for now."
      );
    }
    throw error;
  }
  const presentationId = initPayload?.presentation_id;
  if (!presentationId) {
    throw new Error("Unable to initialize chunked upload.");
  }

  for (let chunkIndex = 0; chunkIndex < totalChunks; chunkIndex += 1) {
    const start = chunkIndex * CHUNK_SIZE_BYTES;
    const end = Math.min(file.size, start + CHUNK_SIZE_BYTES);
    const chunkBlob = file.slice(start, end);
    const chunkForm = new FormData();
    chunkForm.append("chunk_index", String(chunkIndex));
    chunkForm.append("chunk", chunkBlob, `${file.name}.part-${chunkIndex}`);
    await request(`/api/v1/presentations/${presentationId}/chunk`, { method: "POST", body: chunkForm }, API_UPLOAD_TIMEOUT_MS);
  }

  const completeResponse = await request(
    `/api/v1/presentations/${presentationId}/complete`,
    { method: "POST" },
    API_UPLOAD_TIMEOUT_MS
  );
  return completeResponse.json();
}

export { base as apiBase };
