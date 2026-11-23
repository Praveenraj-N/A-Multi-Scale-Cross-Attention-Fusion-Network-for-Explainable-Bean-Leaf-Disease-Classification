import { useState } from "react";
import { LoaderCircle, LocateFixed } from "lucide-react";
import { Panel } from "../ui";
import { parseCoordinate } from "../../data/outbreak";
import { createPlantation } from "../../services/outbreakApi";
import { getBrowserLocation } from "../../services/geolocation";

const inputClass =
  "w-full rounded-lg border border-line bg-ground px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-leaf focus:outline-none";

export default function PlantationForm({ canWrite, onCreated }) {
  const [form, setForm] = useState({ name: "", crop: "common_bean", lat: "", lon: "", variety: "", plantingDate: "" });
  const [errors, setErrors] = useState({});
  const [status, setStatus] = useState({ state: "idle", message: null });
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  if (!canWrite) return null;

  const locate = async () => {
    try {
      const pos = await getBrowserLocation();
      set({ lat: pos.lat.toFixed(5), lon: pos.lon.toFixed(5) });
    } catch (err) {
      setStatus({ state: "error", message: err.message });
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    const la = parseCoordinate(form.lat, "lat");
    const lo = parseCoordinate(form.lon, "lon");
    const next = {};
    if (la.error) next.lat = la.error;
    if (lo.error) next.lon = lo.error;
    setErrors(next);
    if (Object.keys(next).length) return;

    setStatus({ state: "saving", message: null });
    try {
      const created = await createPlantation({
        name: form.name.trim() || undefined,
        crop_type: form.crop.trim(),
        latitude: la.value,
        longitude: lo.value,
        crop_variety: form.variety.trim() || undefined,
        planting_date: form.plantingDate || undefined
      });
      setStatus({ state: "saved", message: `Registered ${created.alias}.` });
      setForm((f) => ({ ...f, name: "", lat: "", lon: "", variety: "", plantingDate: "" }));
      onCreated?.(created);
    } catch (err) {
      setStatus({ state: "error", message: err.message });
    }
  };

  return (
    <Panel title="Register a plantation" description="Registered plantations appear on the map with an inspection priority. The name is visible only to key holders.">
      <form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="pl-name" className="mb-1.5 block text-sm font-medium text-ink">Name or identifier</label>
          <input id="pl-name" className={inputClass} value={form.name} onChange={(e) => set({ name: e.target.value })} maxLength={120} />
        </div>
        <div>
          <label htmlFor="pl-crop" className="mb-1.5 block text-sm font-medium text-ink">Crop type</label>
          <input id="pl-crop" className={inputClass} value={form.crop} onChange={(e) => set({ crop: e.target.value })} />
        </div>
        <div>
          <label htmlFor="pl-lat" className="mb-1.5 block text-sm font-medium text-ink">Latitude</label>
          <input id="pl-lat" inputMode="decimal" className={inputClass} value={form.lat} onChange={(e) => set({ lat: e.target.value })} />
          {errors.lat && <p className="mt-1 text-xs text-alert" role="alert">{errors.lat}</p>}
        </div>
        <div>
          <label htmlFor="pl-lon" className="mb-1.5 block text-sm font-medium text-ink">Longitude</label>
          <input id="pl-lon" inputMode="decimal" className={inputClass} value={form.lon} onChange={(e) => set({ lon: e.target.value })} />
          {errors.lon && <p className="mt-1 text-xs text-alert" role="alert">{errors.lon}</p>}
        </div>
        <div>
          <label htmlFor="pl-var" className="mb-1.5 block text-sm font-medium text-ink">Crop variety (optional)</label>
          <input id="pl-var" className={inputClass} value={form.variety} onChange={(e) => set({ variety: e.target.value })} />
        </div>
        <div>
          <label htmlFor="pl-date" className="mb-1.5 block text-sm font-medium text-ink">Planting date (optional)</label>
          <input id="pl-date" type="date" className={inputClass} value={form.plantingDate} max={new Date().toISOString().slice(0, 10)} onChange={(e) => set({ plantingDate: e.target.value })} />
        </div>
        <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
          <button type="submit" disabled={status.state === "saving"} className="inline-flex items-center gap-2 rounded-xl bg-leaf px-4 py-2.5 text-sm font-semibold text-ground hover:bg-leaf/90 disabled:bg-raised disabled:text-ink-3">
            {status.state === "saving" && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
            Register plantation
          </button>
          <button type="button" onClick={locate} className="inline-flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm text-ink-2 hover:text-ink">
            <LocateFixed className="size-4" aria-hidden /> Use my location
          </button>
          <span role="status" aria-live="polite" className={`text-sm ${status.state === "error" ? "text-alert" : "text-leaf"}`}>{status.message}</span>
        </div>
      </form>
    </Panel>
  );
}
