import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router";
import { Crosshair, LocateFixed, LoaderCircle, RefreshCw, RotateCcw } from "lucide-react";
import AccessBar from "../components/outbreak/AccessBar";
import HistoryPanel from "../components/outbreak/HistoryPanel";
import MapFilters from "../components/outbreak/MapFilters";
import MapLegend from "../components/outbreak/MapLegend";
import ObservationForm from "../components/outbreak/ObservationForm";
import OutbreakMap from "../components/outbreak/OutbreakMap";
import PlantationForm from "../components/outbreak/PlantationForm";
import RiskPanel, { RiskBadge } from "../components/outbreak/RiskPanel";
import SummaryCards from "../components/outbreak/SummaryCards";
import { Notice, PageHeader, Panel } from "../components/ui";
import { DEFAULT_FILTERS, WEATHER_STATUS_TEXT } from "../data/outbreak";
import { useAccess, useOutbreakData } from "../hooks/useOutbreakData";
import { getBrowserLocation } from "../services/geolocation";
import { KEY_REJECTED_EVENT, getAccessKey, getNearbyPlantations } from "../services/outbreakApi";

const DEFAULT_NEARBY_KM = 10;

export default function OutbreakMonitoring() {
  const routeState = useLocation().state;
  const prefill = routeState?.prefill;

  const [accessKey, setAccessKey] = useState(getAccessKey);
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [selectedId, setSelectedId] = useState(null);
  const [asOf, setAsOf] = useState(null);
  const [pickMode, setPickMode] = useState(false);
  const [picked, setPicked] = useState(null);
  const [userLocation, setUserLocation] = useState(null);
  const [locationError, setLocationError] = useState(null);
  const [locating, setLocating] = useState(false);
  const [nearby, setNearby] = useState({ status: "idle", items: [], error: null });
  const [keyRejected, setKeyRejected] = useState(false);
  const mapRef = useRef(null);

  useEffect(() => {
    const onRejected = () => {
      setKeyRejected(true);
      setAccessKey("");
    };
    window.addEventListener(KEY_REJECTED_EVENT, onRejected);
    return () => window.removeEventListener(KEY_REJECTED_EVENT, onRejected);
  }, []);

  const { access } = useAccess(accessKey);
  const { status, data, history, historyError, error, refresh } = useOutbreakData(filters, accessKey);
  const canWrite = access?.role === "admin" && access?.writes_enabled;

  const plantations = data?.plantations ?? [];
  const selected = plantations.find((p) => p.id === selectedId) ?? null;

  // Time slider: hide observations after the chosen day (client-side view only)
  const visibleObservations = useMemo(() => {
    const all = data?.observations ?? [];
    const period = asOf != null ? history?.series?.[asOf]?.period : null;
    if (!period) return all;
    const cutoff = new Date(`${period}T23:59:59.999Z`).getTime();
    return all.filter((o) => new Date(o.observed_at).getTime() <= cutoff);
  }, [data, history, asOf]);

  // Proximity-search centre: picked point > my location > selected plantation
  const centre = picked ?? userLocation ?? (selected ? { lat: selected.latitude, lon: selected.longitude } : null);
  const radiusKm = filters.radiusKm > 0 ? filters.radiusKm : DEFAULT_NEARBY_KM;

  useEffect(() => {
    if (!centre) {
      setNearby({ status: "idle", items: [], error: null });
      return undefined;
    }
    const ctl = new AbortController();
    setNearby((n) => ({ ...n, status: "loading", error: null }));
    getNearbyPlantations(centre.lat, centre.lon, radiusKm, { signal: ctl.signal })
      .then((res) => setNearby({ status: "ready", items: res.items, error: null }))
      .catch((err) => {
        if (err.name !== "AbortError") setNearby({ status: "error", items: [], error: err });
      });
    return () => ctl.abort();
  }, [centre?.lat, centre?.lon, radiusKm, accessKey, data]); // eslint-disable-line react-hooks/exhaustive-deps

  const riskById = useMemo(() => Object.fromEntries(plantations.map((p) => [p.id, p.risk?.overall])), [plantations]);

  const locate = async () => {
    setLocating(true);
    setLocationError(null);
    try {
      const pos = await getBrowserLocation();
      setUserLocation({ lat: pos.lat, lon: pos.lon });
      setPicked(null);
      mapRef.current?.flyTo(pos.lat, pos.lon, 11);
    } catch (err) {
      setLocationError(err.message);
    } finally {
      setLocating(false);
    }
  };

  const loading = status === "loading";

  return (
    <>
      <PageHeader
        title="Outbreak Monitoring"
        lead="Reported leaf-disease detections, nearby plantations and a preliminary inspection-priority index on one map. Priority shows where a visit may be worthwhile; it does not mean a plantation is infected."
        actions={
          <button type="button" onClick={refresh} className="inline-flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm text-ink-2 hover:text-ink" disabled={loading}>
            <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} aria-hidden /> Refresh data
          </button>
        }
      />

      <AccessBar access={access} accessKey={accessKey} onKeyChange={(k) => { setKeyRejected(false); setAccessKey(k); }} />

      {keyRejected && (
        <Notice tone="warn" title="Access key not accepted" className="mb-6">
          The saved key didn't match the server's key, so you're now in the public view. Start the backend with OUTBREAK_ADMIN_API_KEY set to
          your key, then enter that same key above.
        </Notice>
      )}

      {status === "error" && (
        <Notice tone="error" title={error?.offline ? "The API is offline" : "Couldn't load map data"} className="mb-6">
          {error?.message}
          {data && " Showing the last data that loaded."}
        </Notice>
      )}

      {data && data.weather.status !== "ok" && data.weather.status !== "not_requested" && (
        <Notice tone="warn" title="Environmental assessment incomplete" className="mb-6">
          {WEATHER_STATUS_TEXT[data.weather.status]} Surveillance and case-based priority still work.
        </Notice>
      )}

      <SummaryCards summary={data?.summary} loading={loading} />

      <div className="mt-6 grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Panel title="Filters" bodyClassName="pt-4">
          <MapFilters filters={filters} onChange={setFilters} onReset={() => setFilters(DEFAULT_FILTERS)} />
        </Panel>

        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap gap-2" role="toolbar" aria-label="Map controls">
            <button type="button" onClick={() => mapRef.current?.resetView()} className="inline-flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm text-ink-2 hover:text-ink">
              <RotateCcw className="size-4" aria-hidden /> Reset view
            </button>
            <button type="button" onClick={locate} disabled={locating} className="inline-flex items-center gap-2 rounded-lg border border-line px-3 py-2 text-sm text-ink-2 hover:text-ink disabled:opacity-60">
              {locating ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <LocateFixed className="size-4" aria-hidden />} Show my location
            </button>
            <button
              type="button"
              onClick={() => setPickMode((m) => !m)}
              aria-pressed={pickMode}
              className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${pickMode ? "border-xai bg-xai-dim/40 text-ink" : "border-line text-ink-2 hover:text-ink"}`}
            >
              <Crosshair className="size-4" aria-hidden /> {pickMode ? "Click the map to set a search point" : "Search around a point"}
            </button>
            {(picked || userLocation) && (
              <button type="button" onClick={() => { setPicked(null); setUserLocation(null); }} className="rounded-lg border border-line px-3 py-2 text-sm text-ink-2 hover:text-ink">
                Clear search point
              </button>
            )}
          </div>
          {locationError && <Notice tone="warn" title="Location unavailable">{locationError}</Notice>}

          <div className="relative">
            <OutbreakMap
              ref={mapRef}
              observations={visibleObservations}
              plantations={plantations}
              selectedPlantationId={selectedId}
              onSelectPlantation={setSelectedId}
              searchArea={centre ? { ...centre, radiusKm } : null}
              userLocation={userLocation}
              pickMode={pickMode}
              onPick={(p) => { setPicked(p); setPickMode(false); }}
            />
            {loading && (
              <div className="pointer-events-none absolute left-3 top-3 z-[500] flex items-center gap-2 rounded-lg bg-panel/90 px-3 py-1.5 text-sm text-ink-2" role="status">
                <LoaderCircle className="size-4 animate-spin" aria-hidden /> Loading map data
              </div>
            )}
            {status === "ready" && data && data.observations.length === 0 && plantations.length === 0 && (
              <div className="pointer-events-none absolute inset-x-4 bottom-4 z-[500] rounded-lg bg-panel/95 px-4 py-3 text-sm text-ink-2" role="status">
                Nothing to show for these filters. No observations or plantations have been recorded yet, or they are filtered out.
              </div>
            )}
          </div>

          {data?.truncated?.observations && (
            <Notice tone="info" title="Showing a subset">
              There are more matching observations than the map loads at once. Narrow the date range or filters to see the rest.
            </Notice>
          )}
          {data?.truncated?.plantations && (
            <Notice tone="info" title="Showing a subset of plantations">Only the first plantations are assessed per view. Narrow the filters to see the rest.</Notice>
          )}

          <MapLegend />
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <RiskPanel plantation={selected} filters={filters} accessKey={accessKey} />

        <Panel
          title="Nearby plantations"
          description={centre ? `Within ${radiusKm} km of the search point. This is a proximity search, not a model of disease spread.` : "Set a search point (your location, a point on the map, or a selected plantation) to list nearby plantations."}
        >
          {nearby.status === "loading" && <p className="flex items-center gap-2 text-sm text-ink-2" role="status"><LoaderCircle className="size-4 animate-spin" aria-hidden /> Searching</p>}
          {nearby.status === "error" && <Notice tone="error" title="Search failed">{nearby.error.message}</Notice>}
          {nearby.status === "ready" && nearby.items.length === 0 && <p className="text-sm text-ink-3">No registered plantations within {radiusKm} km.</p>}
          {nearby.items.length > 0 && (
            <ul className="divide-y divide-line">
              {nearby.items.map((p) => (
                <li key={p.id}>
                  <button type="button" onClick={() => { setSelectedId(p.id); mapRef.current?.flyTo(p.latitude, p.longitude, 13); }} className="flex w-full flex-wrap items-center justify-between gap-2 py-2.5 text-left text-sm hover:bg-raised/50">
                    <span className="text-ink">{p.alias} <span className="text-ink-3">· {p.crop_type.replace(/_/g, " ")}</span></span>
                    <span className="flex items-center gap-3">
                      {riskById[p.id] && <RiskBadge category={riskById[p.id].category} />}
                      <span className="num text-ink-3">{p.distance_km} km</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="mt-6">
        <HistoryPanel history={history} error={historyError} loading={loading} asOf={asOf} onAsOfChange={setAsOf} />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <ObservationForm key={prefill ? `${prefill.disease}-${prefill.confidence}` : "blank"} plantations={plantations} prefill={prefill} canWrite={canWrite} onCreated={refresh} />
        <PlantationForm canWrite={canWrite} onCreated={refresh} />
      </div>

      <p className="mt-8 text-xs leading-relaxed text-ink-3">
        Limitations: the index is a transparent, rule-based baseline with provisional, unvalidated thresholds. It is not a validated model of
        disease transmission and its score is not an infection probability. Unverified model detections are weighted below confirmed cases.
        Reliable outbreak prediction needs verified, georeferenced field records over time.
      </p>
    </>
  );
}
