import { CircleCheck, CircleX, FlaskConical, LoaderCircle } from "lucide-react";

// Backend/model status from the live /health endpoint (never assumed).
export default function StatusBadge({ health, compact = false }) {
  const { status, data } = health;

  const variants = {
    checking: { icon: LoaderCircle, text: "Checking API", cls: "text-ink-3 border-line", spin: true },
    loading: { icon: LoaderCircle, text: "Model loading", cls: "text-amber border-amber-dim", spin: true },
    ready: {
      icon: CircleCheck,
      text: data?.device === "cuda" ? "GPU model ready" : "CPU model ready",
      cls: "text-leaf border-leaf-dim"
    },
    offline: { icon: CircleX, text: "API offline", cls: "text-alert border-alert/40" },
    mock: { icon: FlaskConical, text: "Mock mode", cls: "text-amber border-amber/50" }
  };

  const v = variants[status] ?? variants.checking;
  const Icon = v.icon;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border bg-ground/60 ${compact ? "px-2.5 py-1 text-xs" : "px-3 py-1.5 text-sm"} font-medium ${v.cls}`}
      role="status"
    >
      <Icon className={`size-3.5 ${v.spin ? "animate-spin" : ""}`} aria-hidden />
      {v.text}
    </span>
  );
}
