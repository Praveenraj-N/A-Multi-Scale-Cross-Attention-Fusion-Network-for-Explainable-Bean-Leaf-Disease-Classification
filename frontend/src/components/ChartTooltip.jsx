// Shared tooltip body for Recharts charts: text in ink tokens, colour only in the swatch.
export default function ChartTooltip({ active, payload, label, title, labelFormat, format = (v) => v, rows }) {
  if (!active || !payload?.length) return null;

  const items = rows ? rows(payload) : payload.map((p) => ({ name: p.name, value: format(p.value, p), color: p.color || p.payload?.fill }));
  const heading = title ?? (rows ? null : labelFormat ? labelFormat(label) : label);

  return (
    <div className="rounded-lg border border-line-strong bg-raised/95 px-3 py-2 text-xs shadow-lg shadow-black/30 backdrop-blur">
      {heading != null && heading !== "" && <p className="mb-1 font-semibold text-ink">{heading}</p>}
      {items.map((item) => (
        <p key={item.name} className="num flex items-center gap-2 text-ink-2">
          {item.color && <span className="size-2 rounded-full" style={{ background: item.color }} aria-hidden />}
          <span>{item.name}</span>
          <span className="ml-auto pl-3 font-medium text-ink">{item.value}</span>
        </p>
      ))}
    </div>
  );
}
