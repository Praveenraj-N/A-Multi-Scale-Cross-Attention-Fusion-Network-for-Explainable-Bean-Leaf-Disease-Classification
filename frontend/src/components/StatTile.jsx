export default function StatTile({ icon: Icon, value, label, note, tone = "leaf", emphasis = false }) {
  const toneClass = {
    leaf: "text-leaf",
    xai: "text-xai",
    amber: "text-amber",
    muted: "text-ink-3"
  }[tone];

  return (
    <div className={`panel flex min-w-0 flex-col justify-between gap-4 p-5 ${emphasis ? "border-leaf-dim" : ""}`}>
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-ink-2">{label}</p>
        {Icon && <Icon className={`size-4 ${toneClass}`} aria-hidden />}
      </div>
      <div>
        <p className={`num font-display font-semibold leading-none text-ink ${emphasis ? "text-[2.6rem]" : "text-3xl"}`}>{value}</p>
        {note && <p className="mt-2 text-xs leading-relaxed text-ink-3">{note}</p>}
      </div>
    </div>
  );
}
