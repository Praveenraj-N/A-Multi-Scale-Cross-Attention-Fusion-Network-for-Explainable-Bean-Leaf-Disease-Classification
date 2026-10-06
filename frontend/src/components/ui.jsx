// Small shared building blocks used across pages.

import { CircleAlert, FlaskConical, Info, TriangleAlert } from "lucide-react";
import { classColor, classLabel } from "../data/classes";

export function PageHeader({ title, lead, actions }) {
  return (
    <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="max-w-2xl">
        <h1 className="text-3xl font-semibold text-ink md:text-[2.5rem] md:leading-[1.1]">{title}</h1>
        {lead && <p className="mt-3 text-[15px] leading-relaxed text-ink-2">{lead}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-3">{actions}</div>}
    </header>
  );
}

export function Panel({ title, description, action, children, className = "", bodyClassName = "", as: Tag = "section" }) {
  return (
    <Tag className={`panel min-w-0 ${className}`}>
      {(title || action) && (
        <div className="flex items-start justify-between gap-4 px-5 pt-5">
          <div>
            {title && <h2 className="text-lg font-semibold text-ink">{title}</h2>}
            {description && <p className="mt-1 text-sm leading-relaxed text-ink-3">{description}</p>}
          </div>
          {action}
        </div>
      )}
      <div className={`p-5 ${bodyClassName}`}>{children}</div>
    </Tag>
  );
}

const NOTICE_TONES = {
  info: { icon: Info, box: "border-line-strong bg-raised", iconColor: "text-ink-2" },
  xai: { icon: Info, box: "border-xai-dim bg-xai-dim/25", iconColor: "text-xai" },
  warn: { icon: TriangleAlert, box: "border-amber-dim bg-amber-dim/30", iconColor: "text-amber" },
  error: { icon: CircleAlert, box: "border-alert/40 bg-alert/10", iconColor: "text-alert" },
  mock: { icon: FlaskConical, box: "border-amber/50 bg-amber-dim/40", iconColor: "text-amber" }
};

export function Notice({ tone = "info", title, children, className = "" }) {
  const { icon: Icon, box, iconColor } = NOTICE_TONES[tone];
  return (
    <div className={`flex gap-3 rounded-xl border px-4 py-3 text-sm leading-relaxed ${box} ${className}`} role={tone === "error" ? "alert" : undefined}>
      <Icon className={`mt-0.5 size-4 shrink-0 ${iconColor}`} aria-hidden />
      <div className="text-ink-2">
        {title && <p className="font-semibold text-ink">{title}</p>}
        {children}
      </div>
    </div>
  );
}

export function ClassChip({ id, size = "sm" }) {
  const big = size === "lg";
  return (
    <span className={`inline-flex items-center gap-2 ${big ? "text-base" : "text-sm"} text-ink`}>
      <span
        className={`${big ? "size-3" : "size-2.5"} shrink-0 rounded-full`}
        style={{ background: classColor(id) }}
        aria-hidden
      />
      {classLabel(id)}
    </span>
  );
}

export function KeyValueList({ items, className = "" }) {
  return (
    <dl className={`divide-y divide-line ${className}`}>
      {items.map(({ label, value, hint }) => (
        <div key={label} className="flex items-baseline justify-between gap-4 py-2.5 text-sm">
          <dt className="text-ink-3">{label}</dt>
          <dd className="num text-right font-medium text-ink">
            {value}
            {hint && <span className="block text-xs font-normal text-ink-3">{hint}</span>}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function Figure({ src, alt, caption, source, className = "" }) {
  return (
    <figure className={`overflow-hidden rounded-xl border border-line bg-white/[0.03] ${className}`}>
      <img src={src} alt={alt} loading="lazy" className="w-full bg-white object-contain" />
      {(caption || source) && (
        <figcaption className="px-4 py-3 text-sm text-ink-2">
          {caption}
          {source && <span className="mt-0.5 block text-xs text-ink-3">Source: {source}</span>}
        </figcaption>
      )}
    </figure>
  );
}

export function ImageTile({ src, alt, label, note, fit = "cover", className = "" }) {
  return (
    <figure className={`flex flex-col gap-2 ${className}`}>
      <div className="aspect-square overflow-hidden rounded-xl border border-line bg-raised">
        {src ? (
          <img src={src} alt={alt} className={`size-full ${fit === "fill" ? "object-fill" : fit === "contain" ? "object-contain" : "object-cover"}`} />
        ) : (
          <div className="grid size-full place-items-center px-4 text-center text-sm text-ink-3">{note || "Not available"}</div>
        )}
      </div>
      <figcaption className="text-sm">
        <span className="font-medium text-ink">{label}</span>
        {src && note && <span className="block text-xs text-ink-3">{note}</span>}
      </figcaption>
    </figure>
  );
}

export function formatPercent(value, digits = 2) {
  if (value == null || Number.isNaN(value)) return "—";
  const pct = value * 100;
  const floor = 1 / 10 ** digits;
  if (pct > 0 && pct < floor) return `<${floor}%`;
  // A probability below 1 must never display as 100%
  if (pct < 100 && Number(pct.toFixed(digits)) >= 100) return `>${(100 - floor).toFixed(digits)}%`;
  return `${pct.toFixed(digits)}%`;
}
