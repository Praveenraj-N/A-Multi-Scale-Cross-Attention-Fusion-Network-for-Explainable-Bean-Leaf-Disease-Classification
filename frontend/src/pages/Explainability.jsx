import { Link } from "react-router";
import { ScanLine } from "lucide-react";
import CompareSlider from "../components/CompareSlider";
import { Figure, ImageTile, Notice, PageHeader, Panel } from "../components/ui";
import { useAnalysis } from "../context/AnalysisContext";
import { classLabel } from "../data/classes";

const STEPS = [
  {
    title: "Forward pass",
    text: "The leaf image runs through MSCAF-Net. At the fused 7×7 map (layer fusion_identity) the activations of all 128 channels are recorded."
  },
  {
    title: "Backward pass",
    text: "The score of the predicted class is back-propagated to that same layer, giving the gradient of the class score for every channel and position."
  },
  {
    title: "Channel weights",
    text: "Each channel's gradients are averaged over the 7×7 grid. Channels whose activation raises the class score get a higher weight."
  },
  {
    title: "Heatmap",
    text: "The weighted channels are summed, negative values are set to zero, and the 7×7 map is upsampled to 224×224 and scaled to the 0–1 range."
  }
];

const LIMITS = [
  "It is qualitative: it shows where the model's evidence was concentrated, not what the disease looks like or where it is.",
  "It is not a segmentation of lesions or pustules, and highlighted regions are not exact disease locations.",
  "It does not prove causation. A highlighted region is associated with the prediction; it is not shown to have caused it.",
  "Its resolution is coarse. Each cell of the 7×7 map covers about 32×32 pixels of the 224×224 input, so small lesions can't be resolved individually.",
  "It explains only the 7×7 scale. The 28×28 and 14×14 scales also feed the classifier but aren't part of this heatmap."
];

function CurrentExample({ current }) {
  const g = current.result.gradcam;
  if (g?.status !== "success") {
    return (
      <Notice tone="info" title="Your latest analysis has no Grad-CAM">
        Run a new analysis with Grad-CAM turned on to see it explained here.
      </Notice>
    );
  }

  return (
    <div>
      {current.result.isMock && (
        <Notice tone="mock" title="Mock data" className="mb-5">
          These images are the replayed mock sample, not output for an uploaded image.
        </Notice>
      )}
      <div className="grid gap-4 sm:grid-cols-3">
        <ImageTile src={current.imageUrl} alt="Original leaf" label="Original image" note={current.fileName} fit="fill" />
        <ImageTile src={g.heatmap_url} alt="Grad-CAM heatmap" label="Heatmap" note={`Target class: ${classLabel(g.target_class)}`} fit="fill" />
        <ImageTile src={g.overlay_url} alt="Grad-CAM overlay" label="Overlay" note="Heatmap at 40% over the input" fit="fill" />
      </div>
      <div className="mx-auto mt-6 max-w-md">
        <CompareSlider before={current.imageUrl} after={g.overlay_url} />
      </div>
    </div>
  );
}

export default function Explainability() {
  const { current } = useAnalysis();

  return (
    <>
      <PageHeader
        title="Explainable AI"
        lead="Grad-CAM provides a qualitative visualization of spatial regions that influenced the model's prediction. Use it to check whether the model is looking at the leaf, not to locate disease."
      />

      <div className="mb-6 grid gap-6 lg:grid-cols-5">
        <Panel className="lg:col-span-3" title="How Grad-CAM works in MSCAF-Net">
          <ol className="space-y-4">
            {STEPS.map((step, i) => (
              <li key={step.title} className="grid grid-cols-[2rem_1fr] gap-3">
                <span className="num grid size-8 place-items-center rounded-full border border-xai/50 bg-xai-dim/30 text-sm font-semibold text-xai">{i + 1}</span>
                <div>
                  <p className="font-medium text-ink">{step.title}</p>
                  <p className="mt-0.5 text-sm leading-relaxed text-ink-2">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </Panel>

        <Panel className="lg:col-span-2" title="Target layer">
          <p className="rounded-lg border border-xai/40 bg-xai-dim/25 px-3 py-2 text-[15px] font-semibold text-xai">fusion_identity</p>
          <p className="mt-4 text-sm leading-relaxed text-ink-2">
            An identity layer placed on the fused 7×7 feature map, after cross-attention and adaptive fusion of the PVT v2 and GCADSN branches
            at that scale. It changes nothing in the computation; it gives Grad-CAM a fixed point to read activations and gradients from.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-ink-2">
            Because the heatmap comes from this fused 7×7 representation, it reflects both branches together at the coarsest scale.
          </p>
        </Panel>
      </div>

      <Panel
        className="mb-6"
        title={current ? "Your latest analysis" : "Example from the research"}
        description={
          current
            ? "Original image, Grad-CAM heatmap and overlay for the most recent prediction."
            : "One test image per class, generated with the same Grad-CAM implementation. Analyze a leaf to see your own."
        }
        action={
          !current && (
            <Link to="/predict" className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-leaf px-3 py-2 text-sm font-semibold text-ground hover:bg-leaf/90">
              <ScanLine className="size-4" aria-hidden /> Analyze a leaf
            </Link>
          )
        }
      >
        {current ? (
          <CurrentExample current={current} />
        ) : (
          <Figure
            src="/research/gradcam_3class_mscaf_full.png"
            alt="Grad-CAM original, heatmap and overlay for angular leaf spot, bean rust and healthy test images"
            caption="Rows: angular leaf spot, bean rust, healthy. Columns: original, Grad-CAM heatmap, overlay."
            source="results/gradcam_3class_mscaf_full.png"
            className="mx-auto max-w-3xl"
          />
        )}
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Reading the colors">
          <div className="mb-3 h-3 rounded-full" style={{ background: "linear-gradient(90deg,#00008f,#0000ff,#00ffff,#ffff00,#ff0000,#800000)" }} aria-hidden />
          <div className="mb-4 flex justify-between text-xs text-ink-3">
            <span>Weaker influence</span>
            <span>Stronger influence</span>
          </div>
          <p className="text-sm leading-relaxed text-ink-2">
            The heatmap uses the JET colormap. Values are normalized per image, so red means "strongest within this image", not a fixed amount.
            Compare patterns across images, not absolute colors.
          </p>
        </Panel>

        <Panel title="What Grad-CAM can't tell you">
          <ul className="space-y-2.5">
            {LIMITS.map((item) => (
              <li key={item} className="flex gap-2.5 text-sm leading-relaxed text-ink-2">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-amber" aria-hidden />
                {item}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </>
  );
}
