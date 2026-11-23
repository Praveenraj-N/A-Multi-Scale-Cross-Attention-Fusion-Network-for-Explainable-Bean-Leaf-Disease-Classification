import { useEffect, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { KeyValueList, Notice, Panel } from "../ui";
import { WEATHER_STATUS_TEXT, formatDateTime, riskMeta } from "../../data/outbreak";
import { classLabel } from "../../data/classes";
import { getRisk } from "../../services/outbreakApi";

export function RiskBadge({ category }) {
  const meta = riskMeta(category);
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-semibold" style={{ background: meta.color, color: meta.text }}>
      <span aria-hidden>{meta.short}</span>
      {meta.label}
    </span>
  );
}

const WEATHER_ROWS = [
  ["temperature_c", "Temperature", (v) => `${v.toFixed(1)} °C`],
  ["relative_humidity_pct", "Relative humidity", (v) => `${v.toFixed(0)}%`],
  ["rainfall_24h_mm", "Rain, last 24 h", (v) => `${v.toFixed(1)} mm`],
  ["wind_speed_ms", "Wind speed", (v) => `${v.toFixed(1)} m/s`],
  ["wind_direction_deg", "Wind from", (v) => `${v.toFixed(0)}°`]
];

function Assessment({ a }) {
  const dq = a.data_quality;
  return (
    <article className="rounded-xl border border-line bg-ground/40 p-4" aria-label={`${a.disease_label} assessment`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="font-semibold text-ink">{a.disease_label}</h4>
        <RiskBadge category={a.risk_category} />
      </div>
      <p className="mt-2 text-sm leading-relaxed text-ink-2">{a.explanation}</p>
      {a.risk_score != null && (
        <p className="num mt-2 text-xs text-ink-3">
          Preliminary priority index {a.risk_score.toFixed(0)} / 100. This is a ranking aid, not a probability of infection.
        </p>
      )}
      <p className="mt-3 text-sm text-ink">
        <span className="font-medium">Recommended next step: </span>
        {a.recommended_action}
      </p>
      <details className="mt-3 text-xs text-ink-3">
        <summary className="cursor-pointer text-ink-2">Factors and data quality</summary>
        <ul className="mt-2 space-y-1">
          {a.factors.map((f) => (
            <li key={f.name}>
              <span className="text-ink-2">{f.label}:</span>{" "}
              {f.used ? `scored ${(f.normalized * 100).toFixed(0)}% (weight ${f.weight})` : `not used (data missing)`}
            </li>
          ))}
        </ul>
        <p className="mt-2">
          Cases considered: {dq.cases_considered} within {dq.search_distance_km} km over {dq.window_days} days. Data completeness:{" "}
          {dq.level}. Rule version {a.rule_version}.
        </p>
        {dq.missing_factors?.length > 0 && <p className="mt-1">Missing inputs: {dq.missing_factors.join(", ")}.</p>}
      </details>
    </article>
  );
}

export default function RiskPanel({ plantation, filters, accessKey }) {
  const [state, setState] = useState({ status: "idle", data: null, error: null });

  const plantationId = plantation?.id;
  const radius = filters.radiusKm;

  useEffect(() => {
    if (!plantationId) {
      setState({ status: "idle", data: null, error: null });
      return undefined;
    }
    const ctl = new AbortController();
    setState({ status: "loading", data: null, error: null });
    getRisk(plantationId, radius > 0 ? { radius_km: String(radius) } : {}, { signal: ctl.signal })
      .then((data) => setState({ status: "ready", data, error: null }))
      .catch((error) => {
        if (error.name !== "AbortError") setState({ status: "error", data: null, error });
      });
    return () => ctl.abort();
  }, [plantationId, radius, accessKey]);

  if (!plantation) {
    return (
      <Panel title="Risk assessment" description="Select a plantation on the map or in the nearby list to see its assessment.">
        <p className="text-sm text-ink-3">No plantation selected.</p>
      </Panel>
    );
  }

  const { data } = state;
  const weather = data?.weather;

  return (
    <Panel title={`Risk assessment: ${plantation.alias}`} description="Preliminary inspection-priority index from configurable baseline rules. Not a validated infection probability.">
      <div aria-live="polite">
        {state.status === "loading" && (
          <p className="flex items-center gap-2 text-sm text-ink-2" role="status">
            <LoaderCircle className="size-4 animate-spin" aria-hidden /> Assessing nearby reports and conditions
          </p>
        )}
        {state.status === "error" && (
          <Notice tone="error" title="Couldn't load the assessment">
            {state.error.message}
          </Notice>
        )}
      </div>

      {state.status === "ready" && data && (
        <div className="space-y-5">
          <KeyValueList
            items={[
              { label: "Crop", value: plantation.crop_type.replace(/_/g, " ") },
              { label: "Overall priority", value: <RiskBadge category={data.overall.category} />, hint: data.overall.disease_label ? `driven by ${data.overall.disease_label}` : undefined },
              { label: "Assessed", value: formatDateTime(data.assessments[0]?.assessed_at) },
              ...(plantation.name ? [{ label: "Name", value: plantation.name }] : []),
              { label: "Location", value: plantation.coordinates_precise ? "Exact" : "Approximate (privacy-rounded)" }
            ]}
          />

          <div className="space-y-3">{data.assessments.map((a) => <Assessment key={a.disease} a={a} />)}</div>

          <div>
            <h3 className="mb-2 text-[15px] font-semibold text-ink">Environmental conditions</h3>
            {weather?.values ? (
              <>
                <KeyValueList
                  items={WEATHER_ROWS.filter(([k]) => weather.values[k] != null).map(([k, label, fmt]) => ({ label, value: fmt(weather.values[k]) }))}
                />
                <p className="mt-2 text-xs text-ink-3">
                  {weather.kind === "current" ? "Current conditions" : weather.kind} from {weather.source}, valid {formatDateTime(weather.observed_at)}.
                </p>
              </>
            ) : (
              <Notice tone="warn" title="Environmental assessment incomplete">
                {WEATHER_STATUS_TEXT[weather?.status] ?? "Weather data was unavailable."} Risk is based on reported cases only.
              </Notice>
            )}
          </div>

          <div>
            <h3 className="mb-2 text-[15px] font-semibold text-ink">Nearby reported cases</h3>
            {data.assessments.every((a) => a.nearby_cases.length === 0) ? (
              <p className="text-sm text-ink-3">No qualifying reports within the search limits.</p>
            ) : (
              <ul className="divide-y divide-line text-sm">
                {data.assessments.flatMap((a) =>
                  a.nearby_cases.map((c) => (
                    <li key={`${a.disease}-${c.observation_id}`} className="flex flex-wrap justify-between gap-2 py-2 text-ink-2">
                      <span>
                        {classLabel(a.disease)} · {c.verification_status === "confirmed" ? "confirmed" : "unverified model detection"}
                      </span>
                      <span className="num text-ink-3">
                        {c.distance_km} km away · {c.age_days} days ago
                      </span>
                    </li>
                  ))
                )}
              </ul>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}
