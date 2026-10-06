import { ArrowRight } from "lucide-react";
import { ClassChip, Figure, KeyValueList, Notice, PageHeader, Panel } from "../components/ui";
import ConfusionMatrix from "../components/charts/ConfusionMatrix";
import { ABLATION, CONFUSION_MATRIX, FAILURE_CASE } from "../data/research";

export default function FailureAnalysis() {
  const f = FAILURE_CASE;

  return (
    <>
      <PageHeader
        title="Failure Analysis"
        lead="The full model misclassified one of the 128 test images. Looking at it closely shows where the model can still go wrong."
      />

      <div className="mb-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel title="The misclassified image" description={`Test file ${f.file}`}>
          <div className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-4">
            <div>
              <p className="text-xs text-ink-3">True class</p>
              <div className="mt-1"><ClassChip id={f.trueClass} size="lg" /></div>
            </div>
            <ArrowRight className="size-5 text-ink-3" aria-label="predicted as" />
            <div>
              <p className="text-xs text-ink-3">Predicted</p>
              <div className="mt-1"><ClassChip id={f.predictedClass} size="lg" /></div>
            </div>
            <div className="ml-auto rounded-xl border border-amber-dim bg-amber-dim/30 px-4 py-2">
              <p className="text-xs text-ink-3">Confidence of the wrong prediction</p>
              <p className="num font-display text-2xl font-semibold text-ink">{f.confidence.toFixed(2)}%</p>
            </div>
          </div>
          <Figure
            src={f.figure}
            alt="Healthy bean leaf on soil, with a Grad-CAM heatmap for the bean rust class that is strongest on the surrounding soil and shadows"
            caption="Left: original healthy leaf. Middle: Grad-CAM for the predicted bean rust class. Right: overlay."
            source="results/gradcam_misclassified_healthy35.png"
          />
        </Panel>

        <div className="min-w-0 space-y-6">
          <Panel title="Case summary">
            <KeyValueList
              items={[
                { label: "File", value: f.file },
                { label: "True class", value: "Healthy" },
                { label: "Predicted class", value: "Bean rust" },
                { label: "Confidence", value: `${f.confidence.toFixed(2)}%` },
                { label: "Grad-CAM target", value: "Bean rust" }
              ]}
            />
          </Panel>
          <Panel title="Where it sits in the results">
            <ConfusionMatrix matrix={CONFUSION_MATRIX} compact />
          </Panel>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="What the Grad-CAM suggests">
          <p className="text-[15px] leading-relaxed text-ink">
            The Grad-CAM visualization showed relatively broad activation extending beyond the leaf region. This suggests that contextual/background
            features may have contributed to the incorrect prediction, although Grad-CAM alone cannot establish causality.
          </p>
          <p className="mt-4 text-sm leading-relaxed text-ink-2">
            In this image the leaf sits on bare reddish soil with strong shadows, and the leaf itself shows a few small specks. The stronger heatmap
            values fall largely on the soil and shadow around the leaf rather than on the leaf surface.
          </p>
        </Panel>

        <Panel title="Observations">
          <ul className="space-y-3 text-sm leading-relaxed text-ink-2">
            <li className="flex gap-2.5">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-ink-3" aria-hidden />
              The prediction was made with high confidence ({f.confidence.toFixed(2)}%), so a confidence threshold alone would not have caught it.
            </li>
            <li className="flex gap-2.5">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-ink-3" aria-hidden />
              Every ablation variant ({ABLATION.filter((a) => a.confusion).map((a) => a.name).join(", ")}) also predicted exactly one healthy test leaf as
              bean rust. The saved results don't record whether it was the same image.
            </li>
            <li className="flex gap-2.5">
              <span className="mt-2 size-1.5 shrink-0 rounded-full bg-ink-3" aria-hidden />
              A single error on 128 images is too few to draw general conclusions; testing more healthy leaves photographed against bare soil would
              show whether this is a pattern.
            </li>
          </ul>
        </Panel>
      </div>

      <Notice tone="warn" title="Interpretation limits" className="mt-6">
        Grad-CAM shows association, not cause. Confirming that the background drove this error would need a controlled test, for example
        re-running the image with the background masked or cropped.
      </Notice>
    </>
  );
}
