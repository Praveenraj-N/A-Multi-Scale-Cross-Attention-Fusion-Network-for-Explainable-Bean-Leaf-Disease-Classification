// Shared constants and helpers for the Outbreak Monitoring feature.

// Risk categories describe an estimated INSPECTION PRIORITY, never a verified
// infection. Each has a text label and a glyph so colour is never the only cue.
export const RISK_CATEGORIES = [
  { id: "very_high", label: "Very high priority", short: "VH", color: "#e8590c", text: "#ffffff" },
  { id: "high", label: "High priority", short: "H", color: "#f08c2e", text: "#1a1206" },
  { id: "moderate", label: "Moderate priority", short: "M", color: "#e3c33b", text: "#1a1606" },
  { id: "low", label: "Low priority", short: "L", color: "#3dbe7a", text: "#06180e" },
  { id: "insufficient_data", label: "Insufficient data", short: "?", color: "#8a9a92", text: "#0d1411" }
];

export const RISK_BY_ID = Object.fromEntries(RISK_CATEGORIES.map((c) => [c.id, c]));

export function riskMeta(id) {
  return RISK_BY_ID[id] ?? RISK_BY_ID.insufficient_data;
}

// Reported disease detections are red circles; this is deliberately a different
// shape and colour family from the squares used for predicted risk.
export const DETECTION_COLOR = "#e5484d";

export const VERIFICATION_STATUSES = [
  { id: "confirmed", label: "Confirmed", note: "Checked by an authorised person" },
  { id: "unverified", label: "Unverified model detection", note: "Reported by the model, not yet checked" },
  { id: "rejected", label: "Rejected", note: "Checked and found incorrect" }
];

export const VERIFICATION_LABEL = Object.fromEntries(VERIFICATION_STATUSES.map((v) => [v.id, v.label]));

export const DISEASE_OPTIONS = [
  { id: "angular_leaf_spot", label: "Angular leaf spot" },
  { id: "bean_rust", label: "Bean rust" },
  { id: "healthy", label: "Healthy" }
];

export const LOCATION_SOURCES = [
  { id: "browser_geolocation", label: "My device location" },
  { id: "manual_entry", label: "Enter coordinates" },
  { id: "registered_plantation", label: "Registered plantation" },
  { id: "administrator", label: "Administrator-entered" }
];

export const WEATHER_STATUS_TEXT = {
  ok: "Live weather conditions were used where available.",
  partial: "Weather was available for only some locations; other assessments are incomplete.",
  unavailable: "The weather service could not be reached, so environmental assessments are incomplete.",
  not_configured: "No weather provider is configured, so environmental assessments are incomplete.",
  not_requested: "Weather was not requested for this view.",
  timeout: "The weather service timed out, so the environmental assessment is incomplete.",
  rate_limited: "The weather service rate limit was reached, so the environmental assessment is incomplete.",
  network_error: "The weather service could not be reached, so the environmental assessment is incomplete.",
  invalid_response: "The weather service returned unusable data, so the environmental assessment is incomplete."
};

export const DEFAULT_FILTERS = {
  diseases: ["angular_leaf_spot", "bean_rust", "healthy"],
  verification: ["confirmed", "unverified"],
  risk: [],
  crop: "",
  dateFrom: "",
  dateTo: "",
  radiusKm: 0 // 0 = per-disease default limits
};

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);
}

export function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function parseCoordinate(text, kind) {
  const trimmed = String(text ?? "").trim();
  if (trimmed === "") return { error: `${kind === "lat" ? "Latitude" : "Longitude"} is required.` };
  const value = Number(trimmed);
  if (!Number.isFinite(value)) return { error: `${kind === "lat" ? "Latitude" : "Longitude"} must be a number.` };
  const limit = kind === "lat" ? 90 : 180;
  if (value < -limit || value > limit) {
    return { error: `${kind === "lat" ? "Latitude" : "Longitude"} must be between -${limit} and ${limit}.` };
  }
  return { value };
}

// Local YYYY-MM-DD -> start/end of that day as ISO instants (browser timezone).
export function dayStartIso(dateStr) {
  return dateStr ? new Date(`${dateStr}T00:00:00`).toISOString() : undefined;
}

export function dayEndIso(dateStr) {
  return dateStr ? new Date(`${dateStr}T23:59:59`).toISOString() : undefined;
}

// Build the query for /api/map-data and /api/outbreak-history from UI filters.
export function filtersToParams(filters, { includeRisk = true } = {}) {
  const params = new URLSearchParams();
  const allDiseases = filters.diseases.length === DISEASE_OPTIONS.length;
  // An empty disease/verification selection means "match nothing", sent as an impossible filter by the caller
  if (!allDiseases) filters.diseases.forEach((d) => params.append("disease", d));
  filters.verification.forEach((v) => params.append("verification_status", v));
  filters.risk.forEach((r) => params.append("risk_category", r));
  if (filters.crop.trim()) params.set("crop_type", filters.crop.trim());
  if (filters.dateFrom) params.set("date_from", dayStartIso(filters.dateFrom));
  if (filters.dateTo) params.set("date_to", dayEndIso(filters.dateTo));
  if (filters.radiusKm > 0) params.set("radius_km", String(filters.radiusKm));
  if (!includeRisk) params.set("include_risk", "false");
  return params;
}
