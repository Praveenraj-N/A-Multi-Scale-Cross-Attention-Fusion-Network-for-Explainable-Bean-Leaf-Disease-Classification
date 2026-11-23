import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Notice, Panel } from "../ui";
import { classColor, classLabel } from "../../data/classes";
import { VERIFICATION_LABEL, formatDate, riskMeta } from "../../data/outbreak";

// Recharts needs concrete colour strings for SVG fills; resolve the CSS variables defined in index.css.
const CONFIRMED = "#e5484d";
const UNVERIFIED = "#e3a33b";

function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line-strong bg-panel px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-semibold text-ink">{label}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="text-ink-2">
          {p.name}: <span className="num font-medium text-ink">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

export default function HistoryPanel({ history, error, loading, asOf, onAsOfChange }) {
  if (error && !history) {
    return (
      <Panel title="Reported activity over time">
        <Notice tone="error" title="Couldn't load history">{error.message}</Notice>
      </Panel>
    );
  }

  const series = history?.series ?? [];
  const daily = history?.bucket === "day";
  const max = Math.max(0, series.length - 1);
  const index = asOf == null ? max : Math.min(asOf, max);
  const diseaseTotals = Object.entries(history?.by_disease ?? {});
  const hasData = (history?.total ?? 0) > 0;

  return (
    <Panel
      title="Reported activity over time"
      description="Reports submitted per day, split into confirmed and unverified (model-generated) observations."
      bodyClassName="space-y-5"
    >
      <div aria-busy={loading} className={loading ? "opacity-70" : ""}>
        {!history ? (
          <p className="text-sm text-ink-3" role="status">Loading history</p>
        ) : !hasData ? (
          <p className="rounded-xl border border-dashed border-line-strong p-6 text-center text-sm text-ink-3">
            No observations in this date range. Nothing has been reported, and none are estimated.
          </p>
        ) : (
          <>
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={series} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke="#263530" vertical={false} />
                  <XAxis dataKey="period" tick={{ fill: "#77897f", fontSize: 11 }} tickFormatter={(v) => v.slice(5)} minTickGap={24} />
                  <YAxis allowDecimals={false} tick={{ fill: "#77897f", fontSize: 11 }} />
                  <Tooltip content={<ChartTip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="confirmed" name={VERIFICATION_LABEL.confirmed} stackId="a" fill={CONFIRMED} />
                  <Bar dataKey="unverified" name={VERIFICATION_LABEL.unverified} stackId="a" fill={UNVERIFIED} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <dl className="mt-4 grid gap-3 sm:grid-cols-3">
              {diseaseTotals.map(([id, count]) => (
                <div key={id} className="rounded-lg border border-line bg-ground/40 px-3 py-2">
                  <dt className="flex items-center gap-2 text-sm text-ink-2">
                    <span className="size-2.5 rounded-full" style={{ background: classColor(id) }} aria-hidden />
                    {classLabel(id)}
                  </dt>
                  <dd className="num text-xl font-semibold text-ink">{count}</dd>
                </div>
              ))}
            </dl>
          </>
        )}
      </div>

      {daily && series.length > 1 && (
        <div>
          <label htmlFor="asof" className="mb-1.5 flex justify-between text-sm text-ink-2">
            <span>Show observations up to</span>
            <span className="num font-medium text-ink">{formatDate(series[index]?.period)}</span>
          </label>
          <input
            id="asof"
            type="range"
            min={0}
            max={max}
            value={index}
            onChange={(e) => onAsOfChange(Number(e.target.value) === max ? null : Number(e.target.value))}
            className="w-full accent-[var(--color-xai)]"
            aria-valuetext={formatDate(series[index]?.period)}
          />
          <p className="mt-1 text-xs text-ink-3">Moves the map back in time. Drag fully right to show everything.</p>
        </div>
      )}

      <div>
        <h3 className="mb-2 text-[15px] font-semibold text-ink">Changes in inspection priority</h3>
        {history?.priority_series?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Plantations by inspection priority on days an assessment was stored</caption>
              <thead className="text-xs text-ink-3">
                <tr>
                  <th className="py-1 pr-3 font-medium">Date</th>
                  <th className="py-1 pr-3 font-medium">Assessed</th>
                  {["very_high", "high", "moderate", "low", "insufficient_data"].map((c) => (
                    <th key={c} className="py-1 pr-3 font-medium">{riskMeta(c).label}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="text-ink-2">
                {history.priority_series.map((row) => (
                  <tr key={row.period} className="border-t border-line">
                    <td className="py-1.5 pr-3">{formatDate(row.period)}</td>
                    <td className="num py-1.5 pr-3">{row.plantations_assessed}</td>
                    {["very_high", "high", "moderate", "low", "insufficient_data"].map((c) => (
                      <td key={c} className="num py-1.5 pr-3">{row.by_category[c] ?? 0}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-ink-3">{history?.priority_note ?? "No priority history yet."}</p>
        )}
      </div>

      <Notice tone="info" title="Reading these counts">
        {history?.interpretation_note ??
          "Counts reflect reports submitted. An increase does not by itself show spread or a transmission chain."}
      </Notice>
    </Panel>
  );
}
