import { DEFAULT_FILTERS, DISEASE_OPTIONS, RISK_CATEGORIES, VERIFICATION_STATUSES } from "../../data/outbreak";

const inputClass =
  "w-full rounded-lg border border-line bg-ground px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-leaf focus:outline-none";

function toggle(list, id) {
  return list.includes(id) ? list.filter((x) => x !== id) : [...list, id];
}

function CheckGroup({ legend, options, selected, onChange }) {
  return (
    <fieldset>
      <legend className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-3">{legend}</legend>
      <div className="space-y-1.5">
        {options.map((o) => (
          <label key={o.id} className="flex cursor-pointer items-center gap-2.5 text-sm text-ink-2">
            <input
              type="checkbox"
              className="size-4 accent-[var(--color-leaf)]"
              checked={selected.includes(o.id)}
              onChange={() => onChange(toggle(selected, o.id))}
            />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export default function MapFilters({ filters, onChange, onReset }) {
  const set = (patch) => onChange({ ...filters, ...patch });
  const dateInvalid = filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo;
  const isDefault = JSON.stringify(filters) === JSON.stringify(DEFAULT_FILTERS);

  return (
    <form className="space-y-5" aria-label="Map filters" onSubmit={(e) => e.preventDefault()}>
      <CheckGroup legend="Disease" options={DISEASE_OPTIONS} selected={filters.diseases} onChange={(diseases) => set({ diseases })} />
      <CheckGroup
        legend="Verification status"
        options={VERIFICATION_STATUSES}
        selected={filters.verification}
        onChange={(verification) => set({ verification })}
      />
      <CheckGroup
        legend="Plantation priority"
        options={RISK_CATEGORIES.map((c) => ({ id: c.id, label: c.label }))}
        selected={filters.risk}
        onChange={(risk) => set({ risk })}
      />
      <p className="-mt-3 text-xs text-ink-3">{filters.risk.length === 0 ? "No priority filter: all plantations shown." : "Only plantations in the checked priorities are shown."}</p>

      <div>
        <label htmlFor="flt-crop" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-3">Crop type</label>
        <input id="flt-crop" className={inputClass} placeholder="e.g. common_bean" value={filters.crop} onChange={(e) => set({ crop: e.target.value })} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label htmlFor="flt-from" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-3">From</label>
          <input id="flt-from" type="date" className={inputClass} value={filters.dateFrom} max={filters.dateTo || undefined} onChange={(e) => set({ dateFrom: e.target.value })} />
        </div>
        <div>
          <label htmlFor="flt-to" className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-ink-3">To</label>
          <input id="flt-to" type="date" className={inputClass} value={filters.dateTo} min={filters.dateFrom || undefined} onChange={(e) => set({ dateTo: e.target.value })} />
        </div>
      </div>
      {dateInvalid && (
        <p role="alert" className="-mt-3 text-xs text-alert">
          The start date is after the end date.
        </p>
      )}

      <div>
        <label htmlFor="flt-radius" className="mb-1.5 flex justify-between text-xs font-semibold uppercase tracking-wide text-ink-3">
          <span>Search radius</span>
          <span className="num normal-case text-ink-2">{filters.radiusKm > 0 ? `${filters.radiusKm} km` : "Per-disease default"}</span>
        </label>
        <input
          id="flt-radius"
          type="range"
          min={0}
          max={50}
          step={1}
          value={filters.radiusKm}
          onChange={(e) => set({ radiusKm: Number(e.target.value) })}
          className="w-full accent-[var(--color-xai)]"
          aria-valuetext={filters.radiusKm > 0 ? `${filters.radiusKm} kilometres` : "Per-disease default"}
        />
        <p className="mt-1 text-xs leading-relaxed text-ink-3">
          Limits which reports count towards a plantation's priority and sizes the nearby-plantation search. Disease-specific distance limits still apply.
        </p>
      </div>

      <button
        type="button"
        onClick={onReset}
        disabled={isDefault}
        className="w-full rounded-lg border border-line px-3 py-2 text-sm text-ink-2 hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
      >
        Reset filters
      </button>
    </form>
  );
}
