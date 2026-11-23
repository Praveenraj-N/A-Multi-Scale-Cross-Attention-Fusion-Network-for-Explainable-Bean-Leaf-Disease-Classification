import { useRef, useState } from "react";
import { LoaderCircle, LocateFixed } from "lucide-react";
import { Notice, Panel } from "../ui";
import { DISEASE_OPTIONS, LOCATION_SOURCES, parseCoordinate } from "../../data/outbreak";
import { createObservation } from "../../services/outbreakApi";
import { getBrowserLocation } from "../../services/geolocation";

const inputClass =
  "w-full rounded-lg border border-line bg-ground px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-leaf focus:outline-none";

function localNowInput() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

function newClientId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function Field({ id, label, hint, error, children }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink">{label}</label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-ink-3">{hint}</p>}
      {error && <p className="mt-1 text-xs text-alert" role="alert">{error}</p>}
    </div>
  );
}

export default function ObservationForm({ plantations, prefill, canWrite, onCreated }) {
  const fromModel = Boolean(prefill?.disease);
  const [form, setForm] = useState({
    disease: prefill?.disease ?? "bean_rust",
    confidencePct: prefill?.confidence != null ? (prefill.confidence * 100).toFixed(1) : "",
    detectionSource: fromModel ? "model_detection" : "manual_report",
    locationSource: "manual_entry",
    lat: "",
    lon: "",
    plantationId: "",
    observedAt: localNowInput(),
    crop: "common_bean",
    notes: "",
    verification: "unverified"
  });
  const [errors, setErrors] = useState({});
  const [status, setStatus] = useState({ state: "idle", message: null });
  const [locating, setLocating] = useState(false);
  const clientId = useRef(newClientId());

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const locate = async () => {
    setLocating(true);
    setStatus({ state: "idle", message: null });
    try {
      const pos = await getBrowserLocation();
      set({ lat: pos.lat.toFixed(5), lon: pos.lon.toFixed(5), locationSource: "browser_geolocation" });
      setErrors((e) => ({ ...e, lat: undefined, lon: undefined }));
    } catch (err) {
      setStatus({ state: "error", message: err.message });
    } finally {
      setLocating(false);
    }
  };

  const validate = () => {
    const next = {};
    const usePlantation = form.locationSource === "registered_plantation";
    let lat;
    let lon;
    if (usePlantation) {
      if (!form.plantationId) next.plantationId = "Choose a registered plantation.";
    } else {
      const la = parseCoordinate(form.lat, "lat");
      const lo = parseCoordinate(form.lon, "lon");
      if (la.error) next.lat = la.error;
      if (lo.error) next.lon = lo.error;
      lat = la.value;
      lon = lo.value;
    }
    let confidence;
    if (form.confidencePct.trim() !== "") {
      const pct = Number(form.confidencePct);
      if (!Number.isFinite(pct) || pct < 0 || pct > 100) next.confidencePct = "Confidence must be between 0 and 100.";
      else confidence = pct / 100;
    } else if (form.detectionSource === "model_detection") {
      next.confidencePct = "Enter the model confidence for a model detection.";
    }
    const when = new Date(form.observedAt);
    if (!form.observedAt || Number.isNaN(when.getTime())) next.observedAt = "Enter the observation date and time.";
    else if (when.getTime() > Date.now() + 5 * 60 * 1000) next.observedAt = "The observation can't be in the future.";
    if (!/^[a-z0-9_ -]{2,40}$/i.test(form.crop.trim())) next.crop = "Use 2-40 letters, digits or underscores.";
    if (form.notes.length > 1000) next.notes = "Notes can be at most 1000 characters.";
    return { next, lat, lon, confidence, when, usePlantation };
  };

  const submit = async (e) => {
    e.preventDefault();
    const { next, lat, lon, confidence, when, usePlantation } = validate();
    setErrors(next);
    if (Object.keys(next).length) return;

    setStatus({ state: "saving", message: null });
    try {
      const body = {
        client_id: clientId.current,
        disease: form.disease,
        confidence,
        observed_at: when.toISOString(),
        crop_type: form.crop.trim(),
        notes: form.notes.trim() || undefined,
        detection_source: form.detectionSource,
        location_source: form.locationSource,
        verification_status: form.verification
      };
      if (usePlantation) body.plantation_id = form.plantationId;
      else {
        body.latitude = lat;
        body.longitude = lon;
      }
      const created = await createObservation(body);
      clientId.current = newClientId(); // a new submission needs a new idempotency key
      setStatus({ state: "saved", message: "Observation saved." });
      onCreated?.(created);
    } catch (err) {
      setStatus({ state: "error", message: err.message });
    }
  };

  if (!canWrite) {
    return (
      <Panel title="Register an observation" description="Submit a disease observation with a location.">
        <Notice tone="info" title="Access key needed">
          Enter an access key above to submit observations. Without one you can browse the map in its privacy-limited public view.
        </Notice>
      </Panel>
    );
  }

  const saving = status.state === "saving";

  return (
    <Panel
      title="Register an observation"
      description={fromModel ? "Pre-filled from your latest prediction. The observation is saved as an unverified model detection." : "Record a disease observation with its location. Model detections stay unverified until someone confirms them."}
    >
      <form onSubmit={submit} noValidate className="grid gap-4 md:grid-cols-2">
        <Field id="obs-disease" label="Predicted disease">
          <select id="obs-disease" className={inputClass} value={form.disease} onChange={(e) => set({ disease: e.target.value })}>
            {DISEASE_OPTIONS.map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
          </select>
        </Field>
        <Field id="obs-source" label="Report type">
          <select id="obs-source" className={inputClass} value={form.detectionSource} onChange={(e) => set({ detectionSource: e.target.value })}>
            <option value="model_detection">Model detection</option>
            <option value="manual_report">Manual report</option>
          </select>
        </Field>
        <Field id="obs-conf" label="Model confidence (%)" error={errors.confidencePct} hint="Softmax confidence from the prediction page. Not a probability of spread.">
          <input id="obs-conf" inputMode="decimal" className={inputClass} value={form.confidencePct} onChange={(e) => set({ confidencePct: e.target.value })} />
        </Field>
        <Field id="obs-when" label="Observed at" error={errors.observedAt}>
          <input id="obs-when" type="datetime-local" className={inputClass} value={form.observedAt} onChange={(e) => set({ observedAt: e.target.value })} />
        </Field>

        <fieldset className="md:col-span-2">
          <legend className="mb-2 text-sm font-medium text-ink">Location</legend>
          <div className="mb-3 flex flex-wrap gap-2" role="radiogroup" aria-label="Location source">
            {LOCATION_SOURCES.map((s) => (
              <label key={s.id} className={`cursor-pointer rounded-lg border px-3 py-1.5 text-sm ${form.locationSource === s.id ? "border-leaf bg-leaf-dim/30 text-ink" : "border-line text-ink-2"}`}>
                <input type="radio" name="loc" className="sr-only" checked={form.locationSource === s.id} onChange={() => set({ locationSource: s.id })} />
                {s.label}
              </label>
            ))}
          </div>

          {form.locationSource === "registered_plantation" ? (
            <Field id="obs-plantation" label="Plantation" error={errors.plantationId}>
              <select id="obs-plantation" className={inputClass} value={form.plantationId} onChange={(e) => set({ plantationId: e.target.value })}>
                <option value="">Select a plantation</option>
                {plantations.map((p) => <option key={p.id} value={p.id}>{p.alias} · {p.crop_type.replace(/_/g, " ")}</option>)}
              </select>
              {plantations.length === 0 && <p className="mt-1 text-xs text-ink-3">No plantations are registered yet.</p>}
            </Field>
          ) : (
            <div className="grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-start">
              <Field id="obs-lat" label="Latitude" error={errors.lat}>
                <input id="obs-lat" inputMode="decimal" className={inputClass} placeholder="-90 to 90" value={form.lat} onChange={(e) => set({ lat: e.target.value })} />
              </Field>
              <Field id="obs-lon" label="Longitude" error={errors.lon}>
                <input id="obs-lon" inputMode="decimal" className={inputClass} placeholder="-180 to 180" value={form.lon} onChange={(e) => set({ lon: e.target.value })} />
              </Field>
              <button type="button" onClick={locate} disabled={locating} className="mt-0 inline-flex items-center justify-center gap-2 rounded-lg border border-line px-3 py-2 text-sm text-ink-2 hover:text-ink disabled:opacity-60 sm:mt-7">
                {locating ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <LocateFixed className="size-4" aria-hidden />}
                Use my location
              </button>
            </div>
          )}
          <p className="mt-2 text-xs text-ink-3">Photos don't carry a location here. Your browser only shares it if you allow it.</p>
        </fieldset>

        <Field id="obs-crop" label="Crop type" error={errors.crop}>
          <input id="obs-crop" className={inputClass} value={form.crop} onChange={(e) => set({ crop: e.target.value })} />
        </Field>
        <Field id="obs-verify" label="Verification status" hint="Only mark Confirmed if someone has checked the plants.">
          <select id="obs-verify" className={inputClass} value={form.verification} onChange={(e) => set({ verification: e.target.value })}>
            <option value="unverified">Unverified</option>
            <option value="confirmed">Confirmed</option>
          </select>
        </Field>
        <div className="md:col-span-2">
          <Field id="obs-notes" label="Notes (optional)" error={errors.notes} hint="Avoid personal details.">
            <textarea id="obs-notes" rows={2} maxLength={1000} className={inputClass} value={form.notes} onChange={(e) => set({ notes: e.target.value })} />
          </Field>
        </div>

        <div className="flex flex-wrap items-center gap-3 md:col-span-2">
          <button type="submit" disabled={saving} className="inline-flex items-center gap-2 rounded-xl bg-leaf px-4 py-2.5 text-sm font-semibold text-ground hover:bg-leaf/90 disabled:bg-raised disabled:text-ink-3">
            {saving && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
            {saving ? "Saving" : "Save observation"}
          </button>
          <span role="status" aria-live="polite" className={`text-sm ${status.state === "error" ? "text-alert" : "text-leaf"}`}>
            {status.message}
          </span>
        </div>
      </form>
    </Panel>
  );
}
