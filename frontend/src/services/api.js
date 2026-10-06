// Single place for talking to the MSCAF-Net FastAPI backend.

import { MOCK_PREDICTION } from "../data/mockPrediction";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

// Mock mode is opt-in only, so real use never shows replayed results by accident.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";

export const MAX_UPLOAD_MB = 10;

export const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"];

export class ApiError extends Error {
  constructor(message, { status = null, offline = false } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.offline = offline;
  }
}

async function request(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(
      `Can't reach the MSCAF-Net API at ${API_BASE_URL}. Start the backend and try again.`,
      { offline: true }
    );
  }

  let body = null;

  try {
    body = await response.json();
  } catch {
    // Non-JSON error bodies fall through to the generic message
  }

  if (!response.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : null;
    const fallback = {
      400: "The file couldn't be read as an image.",
      413: `The file is larger than ${MAX_UPLOAD_MB} MB.`,
      422: "The request was missing an image.",
      503: "The model is still loading. Try again in a few seconds."
    }[response.status];

    throw new ApiError(detail || fallback || `The API returned an error (HTTP ${response.status}).`, {
      status: response.status
    });
  }

  return body;
}

export function getHealth(options) {
  return request("/health", options);
}

export function getModelInfo(options) {
  return request("/model-info", options);
}

// Turns the API's base64 PNGs into data URLs the UI can use directly.
function normalizePrediction(raw) {
  const gradcam = raw.gradcam
    ? {
        ...raw.gradcam,
        heatmap_url: raw.gradcam.heatmap_png_base64 ? `data:image/png;base64,${raw.gradcam.heatmap_png_base64}` : null,
        overlay_url: raw.gradcam.overlay_png_base64 ? `data:image/png;base64,${raw.gradcam.overlay_png_base64}` : null
      }
    : null;

  if (gradcam) {
    delete gradcam.heatmap_png_base64;
    delete gradcam.overlay_png_base64;
  }

  return { ...raw, gradcam, isMock: false };
}

export function validateImageFile(file) {
  if (!file) return "Choose an image to analyze.";
  if (!file.type.startsWith("image/")) return "That file isn't an image. Upload a JPG, PNG, WEBP, BMP or TIFF photo of a bean leaf.";
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `That image is larger than ${MAX_UPLOAD_MB} MB. Use a smaller photo.`;
  return null;
}

export async function predictImage(file, { gradcam = true, signal } = {}) {
  if (USE_MOCK) {
    await new Promise((resolve) => setTimeout(resolve, 700));
    return structuredClone(MOCK_PREDICTION);
  }

  const form = new FormData();
  form.append("file", file);

  const raw = await request(`/predict?gradcam=${gradcam ? "true" : "false"}`, {
    method: "POST",
    body: form,
    signal
  });

  return normalizePrediction(raw);
}
