import { ArrowDown, ArrowLeftRight, Eye } from "lucide-react";

// Diagram of the implemented MSCAF-Net (models/mscaf_net.py).
// PVT v2 (transformer) branch = teal, GCADSN (CNN) branch = leaf green.

const PVT_STAGES = [
  { scale: 28, label: "Stage 2", channels: 128 },
  { scale: 14, label: "Stage 3", channels: 320 },
  { scale: 7, label: "Stage 4", channels: 512 }
];

const GCADSN_STAGES = [
  { scale: 28, label: "GSDW block 1", channels: 9 },
  { scale: 14, label: "GSDW block 2", channels: 12 },
  { scale: 7, label: "Global context block", channels: 48 }
];

function Arrow({ label }) {
  return (
    <div className="flex items-center justify-center gap-2 py-2 text-ink-3" aria-hidden>
      <ArrowDown className="size-4" />
      {label && <span className="text-xs">{label}</span>}
    </div>
  );
}

function Node({ title, detail, tone = "neutral", className = "", children }) {
  const tones = {
    neutral: "border-line-strong bg-raised",
    pvt: "border-xai/50 bg-xai-dim/30",
    cnn: "border-leaf/50 bg-leaf-dim/30",
    out: "border-leaf bg-leaf-dim/50"
  };
  return (
    <div className={`rounded-xl border px-4 py-3 ${tones[tone]} ${className}`}>
      <p className="font-display text-[15px] font-semibold text-ink">{title}</p>
      {detail && <p className="mt-0.5 text-xs leading-relaxed text-ink-2">{detail}</p>}
      {children}
    </div>
  );
}

function BranchLane({ tone, name, kind, stages }) {
  const dot = tone === "pvt" ? "bg-xai" : "bg-leaf";
  return (
    <div className={`rounded-2xl border p-4 ${tone === "pvt" ? "border-xai/40 bg-xai-dim/15" : "border-leaf/40 bg-leaf-dim/15"}`}>
      <div className="mb-3 flex items-center gap-2">
        <span className={`size-2.5 rounded-full ${dot}`} aria-hidden />
        <p className="font-display font-semibold text-ink">{name}</p>
      </div>
      <p className="mb-3 text-xs leading-relaxed text-ink-2">{kind}</p>
      <ol className="space-y-1.5">
        {stages.map((s) => (
          <li key={s.scale} className="num flex items-center justify-between rounded-lg bg-ground/50 px-3 py-2 text-sm">
            <span className="text-ink-2">{s.label}</span>
            <span className="text-ink">
              {s.scale}×{s.scale}, {s.channels} ch
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export default function ArchitectureDiagram() {
  return (
    <div className="mx-auto max-w-4xl" role="figure" aria-label="MSCAF-Net architecture diagram">
      <Node title="Input image" detail="RGB leaf photo resized to 224 × 224, ImageNet-normalized" className="mx-auto max-w-sm text-center" />
      <Arrow label="Same image to both branches" />

      <div className="grid gap-4 md:grid-cols-2">
        <BranchLane
          tone="pvt"
          name="PVT v2-B2 branch"
          kind="Pyramid Vision Transformer: models global relationships across the whole leaf."
          stages={PVT_STAGES}
        />
        <BranchLane
          tone="cnn"
          name="GCADSN branch"
          kind="Lightweight CNN (group, shuffle and depthwise-separable convolutions): captures local texture such as lesions and pustules."
          stages={GCADSN_STAGES}
        />
      </div>

      <Arrow label="Multi-scale feature extraction, 1×1 projection of every feature map to 128 channels" />

      <div className="grid gap-3 md:grid-cols-3">
        {[28, 14, 7].map((s) => (
          <div key={s} className={`rounded-2xl border p-3 ${s === 7 ? "border-xai/40" : "border-line"} bg-panel`}>
            <p className="num mb-2 text-center font-display text-lg font-semibold text-ink">
              {s} × {s}
            </p>
            <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-1.5">
              <span className="rounded-md border border-xai/50 bg-xai-dim/30 px-2 py-1.5 text-center text-xs text-ink">PVT</span>
              <ArrowLeftRight className="size-4 text-ink-3" aria-label="attends to each other" />
              <span className="rounded-md border border-leaf/50 bg-leaf-dim/30 px-2 py-1.5 text-center text-xs text-ink">GCADSN</span>
            </div>
            <p className="mt-2 text-center text-xs text-ink-2">Bidirectional cross-attention, 4 heads</p>
            <div className="my-2 border-t border-line" />
            <p className="text-center text-xs text-ink-2">Adaptive branch fusion</p>
            <p className="text-center text-xs text-ink-3">then global average pooling to a 128-d vector</p>
            {s === 7 && (
              <p className="mt-2 flex items-center justify-center gap-1.5 rounded-md bg-xai-dim/40 px-2 py-1 text-xs text-xai">
                <Eye className="size-3.5" aria-hidden />
                Grad-CAM hook: fusion_identity
              </p>
            )}
          </div>
        ))}
      </div>

      <Arrow />
      <Node title="Adaptive multi-scale fusion" detail="Learned, per-image softmax weights combine the three 128-d scale vectors" className="mx-auto max-w-md text-center" />
      <Arrow />
      <Node title="Classifier" detail="Dropout 0.1, then a linear layer from 128 features to 3 classes" className="mx-auto max-w-md text-center" />
      <Arrow />
      <Node title="Disease prediction" detail="Softmax over angular leaf spot, bean rust and healthy" tone="out" className="mx-auto max-w-sm text-center" />
    </div>
  );
}
