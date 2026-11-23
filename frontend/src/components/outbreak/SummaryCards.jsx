// Only metrics the API could actually compute are shown; null becomes an explicit "Not available".
function Card({ label, value, hint }) {
  const available = value != null;
  return (
    <div className="panel p-4">
      <p className="text-sm text-ink-2">{label}</p>
      <p className={`num mt-1 font-display text-3xl font-semibold leading-none ${available ? "text-ink" : "text-ink-3"}`}>
        {available ? value : "—"}
      </p>
      <p className="mt-2 text-xs leading-relaxed text-ink-3">{available ? hint : "Not available: no assessments yet."}</p>
    </div>
  );
}

export default function SummaryCards({ summary, loading }) {
  const s = summary ?? {};
  return (
    <section aria-label="Summary" aria-busy={loading} className={`grid grid-cols-2 gap-3 lg:grid-cols-5 ${loading ? "opacity-70" : ""}`}>
      <Card label="Reported detections" value={s.reported_detections} hint="Disease reports (not healthy), confirmed or unverified." />
      <Card label="Plantations registered" value={s.plantations_registered} hint="Registered plantations in the current view." />
      <Card label="Need inspection" value={s.plantations_requiring_inspection} hint="Moderate priority or above (preliminary index)." />
      <Card label="High-priority locations" value={s.high_priority_locations} hint="High or very high inspection priority." />
      <Card label="Recent observations" value={s.recent_detections_7d} hint="Disease reports in the last 7 days." />
    </section>
  );
}
