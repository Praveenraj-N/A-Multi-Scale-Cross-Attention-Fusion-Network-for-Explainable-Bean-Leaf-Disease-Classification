// Client for the outbreak-monitoring endpoints of the FastAPI backend.
// The access key is typed by the user at runtime and kept only in sessionStorage
// (this tab). It is never bundled into the frontend code.

import { API_BASE_URL, ApiError } from "./api";

const KEY_STORAGE = "mscaf.outbreakKey";

export function getAccessKey() {
  try {
    return sessionStorage.getItem(KEY_STORAGE) || "";
  } catch {
    return "";
  }
}

export function setAccessKey(key) {
  try {
    if (key) sessionStorage.setItem(KEY_STORAGE, key);
    else sessionStorage.removeItem(KEY_STORAGE);
  } catch {
    // Storage blocked: the key just won't persist across reloads
  }
}

function describeDetail(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc: [...], msg: "..."}]
    return detail
      .map((e) => {
        const field = Array.isArray(e.loc) ? e.loc.filter((p) => p !== "body" && p !== "query").join(".") : "";
        const msg = String(e.msg ?? "Invalid value").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join(" ");
  }
  return null;
}

export const KEY_REJECTED_EVENT = "outbreak-key-rejected";

async function request(path, { method = "GET", params, body, signal, key, _retried = false } = {}) {
  const url = `${API_BASE_URL}${path}${params && params.toString() ? `?${params}` : ""}`;
  const headers = {};
  const accessKey = key !== undefined ? key : getAccessKey();
  if (accessKey) headers["X-API-Key"] = accessKey;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(url, { method, headers, signal, body: body !== undefined ? JSON.stringify(body) : undefined });
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(`Can't reach the MSCAF-Net API at ${API_BASE_URL}. Start the backend and try again.`, { offline: true });
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    // Non-JSON error bodies fall back to the generic message
  }

  // A stale or wrong key must not break read-only browsing: drop it, tell the page, and retry as a public viewer
  if (response.status === 401 && accessKey && method === "GET" && !_retried) {
    setAccessKey("");
    window.dispatchEvent(new Event(KEY_REJECTED_EVENT));
    return request(path, { method, params, body, signal, key: "", _retried: true });
  }

  if (!response.ok) {
    const fallback = {
      401: "An access key is required (or the key is wrong).",
      404: "That record was not found.",
      409: "That looks like a duplicate of an existing observation.",
      503: "The outbreak service is unavailable right now. Try again shortly."
    }[response.status];
    const error = new ApiError(describeDetail(data?.detail) || fallback || `The API returned an error (HTTP ${response.status}).`, {
      status: response.status
    });
    error.payload = data;
    throw error;
  }

  return data;
}

export const getAccess = (opts) => request("/api/access", opts);
export const getMapData = (params, opts) => request("/api/map-data", { params, ...opts });
export const getHistory = (params, opts) => request("/api/outbreak-history", { params, ...opts });
export const getRisk = (plantationId, params, opts) => {
  const p = new URLSearchParams(params);
  p.set("plantation_id", plantationId);
  return request("/api/outbreak-risk", { params: p, ...opts });
};
export const getNearbyPlantations = (lat, lon, radiusKm, opts) =>
  request("/api/plantations/nearby", { params: new URLSearchParams({ lat, lon, radius_km: radiusKm }), ...opts });
export const createObservation = (body, opts) => request("/api/observations", { method: "POST", body, ...opts });
export const createPlantation = (body, opts) => request("/api/plantations", { method: "POST", body, ...opts });
export const setVerification = (id, status, opts) =>
  request(`/api/observations/${id}/verification`, { method: "POST", body: { verification_status: status }, ...opts });
export const snapshotRisk = (opts) => request("/api/outbreak-risk/snapshot", { method: "POST", ...opts });
