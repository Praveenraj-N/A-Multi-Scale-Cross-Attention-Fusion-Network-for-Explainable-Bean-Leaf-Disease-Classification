import { Link } from "react-router";
import { ArrowRight } from "lucide-react";
import { PageHeader, Panel } from "../components/ui";
import { FULL_MODEL_METRICS } from "../data/research";

const SECTIONS = [
  {
    title: "Motivation",
    body: [
      "Common bean is a staple food and an important source of income for smallholder farmers, especially in East Africa. Angular leaf spot and bean rust are two fungal diseases that reduce yields when they aren't spotted early.",
      "Expert diagnosis isn't always available in the field, while smartphones are. A model that classifies leaf photos reliably, and shows what it based its decision on, can help farmers and extension workers act sooner."
    ]
  },
  {
    title: "The problem",
    body: [
      "Field photos are messy: varied lighting, soil and other plants in the background, hands holding the leaf. Early symptoms are small, while the overall look of the leaf also matters.",
      "Convolutional networks are good at local texture and transformers at global context. The base PVT v2 + GCADSN network combines both, but fuses only their final feature maps by concatenation, which loses fine detail and treats both branches as equally useful for every image."
    ]
  },
  {
    title: "The MSCAF-Net approach",
    body: [
      "MSCAF-Net keeps the two complementary branches, a PVT v2 transformer and the GCADSN CNN, and changes how they are combined."
    ]
  }
];

const IDEAS = [
  {
    title: "Multi-scale fusion",
    text: "The branches are fused at 28×28, 14×14 and 7×7, so fine lesion detail and whole-leaf context both reach the classifier."
  },
  {
    title: "Cross-attention",
    text: "At each scale the transformer features attend to the CNN features and the reverse, aligning global and local evidence before fusion."
  },
  {
    title: "Adaptive fusion",
    text: "Learned gates weight each branch and each scale per image, instead of fixed concatenation."
  },
  {
    title: "Grad-CAM explainability",
    text: "Every prediction can come with a heatmap of the regions that influenced it, so users can check whether the model looked at the leaf."
  }
];

export default function About() {
  return (
    <>
      <PageHeader
        title="About the project"
        lead="MSCAF-Net: Multi-Scale Cross-Attention Fusion Network for explainable bean leaf disease classification."
      />

      <div className="mx-auto max-w-3xl space-y-10">
        {SECTIONS.map((s) => (
          <section key={s.title}>
            <h2 className="mb-3 text-2xl font-semibold">{s.title}</h2>
            {s.body.map((p) => (
              <p key={p} className="mb-3 text-[15px] leading-[1.7] text-ink-2">{p}</p>
            ))}
          </section>
        ))}

        <div className="grid gap-4 sm:grid-cols-2">
          {IDEAS.map((idea) => (
            <div key={idea.title} className="panel p-5">
              <h3 className="text-[17px] font-semibold text-ink">{idea.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink-2">{idea.text}</p>
            </div>
          ))}
        </div>

        <section>
          <h2 className="mb-3 text-2xl font-semibold">Research contribution</h2>
          <ul className="space-y-3 text-[15px] leading-[1.7] text-ink-2">
            <li>
              A dual-branch architecture that fuses transformer and CNN features at three scales with bidirectional cross-attention and adaptive
              gating.
            </li>
            <li>
              {FULL_MODEL_METRICS.accuracy}% accuracy ({FULL_MODEL_METRICS.correct} of {FULL_MODEL_METRICS.total}) on the frozen iBean test subset,
              compared with 97.66% for the base fusion network.
            </li>
            <li>An ablation study that measures the effect of multi-scale fusion, cross-attention and adaptive fusion separately.</li>
            <li>Grad-CAM explanations for every prediction, plus an analysis of the one remaining test error.</li>
            <li>This web application, which runs the trained model with its explanations through a local API.</li>
          </ul>
        </section>

        <Panel title="Limitations">
          <ul className="space-y-2.5 text-sm leading-relaxed text-ink-2">
            <li>The test subset has 128 images, so one image changes accuracy by 0.78 percentage points.</li>
            <li>The model knows only three classes and will label any image as one of them, including images that aren't bean leaves.</li>
            <li>Grad-CAM is a qualitative aid. It does not segment disease or establish causation.</li>
            <li>Results are for iBean field photos from Uganda; other regions, cameras or bean varieties may perform differently.</li>
          </ul>
        </Panel>

        <div className="flex flex-wrap gap-3">
          <Link to="/architecture" className="inline-flex items-center gap-2 rounded-xl border border-line-strong px-4 py-2.5 text-sm font-medium text-ink hover:bg-raised">
            Model architecture <ArrowRight className="size-3.5" aria-hidden />
          </Link>
          <Link to="/results" className="inline-flex items-center gap-2 rounded-xl border border-line-strong px-4 py-2.5 text-sm font-medium text-ink hover:bg-raised">
            Research results <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        </div>
      </div>
    </>
  );
}
