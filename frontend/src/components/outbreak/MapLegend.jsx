import { DETECTION_COLOR, RISK_CATEGORIES } from "../../data/outbreak";

function Swatch({ children, style, className = "" }) {
  return (
    <span className={`grid size-6 shrink-0 place-items-center text-[10px] font-bold ${className}`} style={style} aria-hidden>
      {children}
    </span>
  );
}

// Colour is never the only cue: every entry has a shape and a text label.
export default function MapLegend() {
  return (
    <details className="group rounded-xl border border-line bg-ground/40 p-4" open>
      <summary className="cursor-pointer select-none text-sm font-semibold text-ink">Map legend</summary>
      <div className="mt-4 grid gap-5 sm:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-3">Reported observations (circles)</h3>
          <ul className="space-y-2 text-sm text-ink-2">
            <li className="flex items-center gap-3">
              <Swatch className="rounded-full" style={{ background: DETECTION_COLOR, border: `3px solid ${DETECTION_COLOR}` }} />
              Confirmed disease detection (solid)
            </li>
            <li className="flex items-center gap-3">
              <Swatch className="rounded-full" style={{ background: "#0d1411", border: `3px dashed ${DETECTION_COLOR}` }} />
              Unverified model detection (hollow, dashed)
            </li>
            <li className="flex items-center gap-3">
              <Swatch className="rounded-full" style={{ background: "#0d1411", border: "3px dashed #2e9f7a" }} />
              Healthy classification
            </li>
          </ul>
        </div>
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-3">Plantations: predicted inspection priority (squares)</h3>
          <ul className="space-y-2 text-sm text-ink-2">
            {RISK_CATEGORIES.map((c) => (
              <li key={c.id} className="flex items-center gap-3">
                <Swatch className="rounded-md border-2 border-black/50" style={{ background: c.color, color: c.text }}>
                  {c.short}
                </Swatch>
                {c.label}
              </li>
            ))}
          </ul>
        </div>
      </div>
      <p className="mt-4 text-xs leading-relaxed text-ink-3">
        Squares show an estimated inspection priority from a preliminary index. They are not verified infections. The dashed teal circle, when
        shown, is a proximity-search area, not a model of how disease spreads. Numbered markers group several nearby items; zoom in to separate
        them.
      </p>
    </details>
  );
}
