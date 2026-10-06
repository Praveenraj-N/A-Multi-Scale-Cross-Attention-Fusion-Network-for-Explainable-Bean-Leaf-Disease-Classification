import { CircleCheck, Minus } from "lucide-react";
import AblationChart from "../components/charts/AblationChart";
import ConfusionMatrix from "../components/charts/ConfusionMatrix";
import TrainingCurves from "../components/charts/TrainingCurves";
import StatTile from "../components/StatTile";
import { ClassChip, Figure, Notice, PageHeader, Panel } from "../components/ui";
import { ABLATION, CLASS_REPORT, CONFUSION_MATRIX, FULL_MODEL_METRICS, RESEARCH_FIGURES, TEST_SET } from "../data/research";

const pct = (v, d = 2) => (v == null ? "—" : `${v.toFixed(d)}%`);

function Check({ on }) {
  return on ? <CircleCheck className="mx-auto size-4 text-leaf" aria-label="Yes" /> : <Minus className="mx-auto size-4 text-ink-3" aria-label="No" />;
}

export default function Results() {
  const m = FULL_MODEL_METRICS;

  return (
    <>
      <PageHeader title="Research Results" lead={`${TEST_SET.statement} All numbers below come from the saved evaluation outputs in results/.`} />

      <section aria-label="Overall metrics" className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatTile label="Accuracy" value={pct(m.accuracy)} emphasis />
        <StatTile label="Precision" value={pct(m.precision)} note="Weighted average" />
        <StatTile label="Recall" value={pct(m.recall)} note="Weighted average" />
        <StatTile label="F1 score" value={pct(m.f1)} note="Weighted average" />
        <StatTile label="Test result" value={`${m.correct} / ${m.total}`} note={`${m.incorrect} image misclassified`} />
      </section>

      <div className="mb-6 grid gap-6 lg:grid-cols-2">
        <Panel title="Per-class metrics" description="Full MSCAF-Net on the test subset.">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] text-sm">
              <thead>
                <tr className="border-b border-line text-right text-xs text-ink-3">
                  <th scope="col" className="py-2 text-left font-normal">Class</th>
                  <th scope="col" className="py-2 font-normal">Precision</th>
                  <th scope="col" className="py-2 font-normal">Recall</th>
                  <th scope="col" className="py-2 font-normal">F1</th>
                  <th scope="col" className="py-2 font-normal">Images</th>
                </tr>
              </thead>
              <tbody className="num divide-y divide-line text-right">
                {CLASS_REPORT.map((row) => (
                  <tr key={row.id}>
                    <th scope="row" className="py-3 text-left font-normal">
                      <ClassChip id={row.id} />
                    </th>
                    <td className="py-3 text-ink">{(row.precision * 100).toFixed(2)}%</td>
                    <td className="py-3 text-ink">{(row.recall * 100).toFixed(2)}%</td>
                    <td className="py-3 text-ink">{(row.f1 * 100).toFixed(2)}%</td>
                    <td className="py-3 text-ink-2">{row.support}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="num border-t border-line-strong text-right text-ink-2">
                <tr>
                  <th scope="row" className="py-3 text-left font-normal">Weighted average</th>
                  <td className="py-3">99.24%</td>
                  <td className="py-3">99.22%</td>
                  <td className="py-3">99.22%</td>
                  <td className="py-3">128</td>
                </tr>
              </tfoot>
            </table>
          </div>
          <p className="mt-4 text-xs leading-relaxed text-ink-3">
            Bean rust precision is below 100% because one healthy leaf was predicted as bean rust; that same image lowers healthy recall.
          </p>
        </Panel>

        <Panel title="Confusion matrix" description="Rows are the true class, columns the predicted class.">
          <ConfusionMatrix matrix={CONFUSION_MATRIX} />
          <p className="mt-3 flex items-center gap-2 text-xs text-ink-3">
            <span className="size-3 rounded border border-amber bg-amber-dim/40" aria-hidden /> Outlined cell: misclassified images
          </p>
        </Panel>
      </div>

      <Panel
        className="mb-6"
        title="Ablation study"
        description="Each variant adds one MSCAF-Net component. All were trained with the same recipe and evaluated on the same 128 test images."
      >
        <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
          <AblationChart height={280} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px] text-sm">
              <thead>
                <tr className="border-b border-line text-xs text-ink-3">
                  <th scope="col" className="py-2 text-left font-normal">Model</th>
                  <th scope="col" className="px-2 py-2 text-center font-normal">Multi-scale</th>
                  <th scope="col" className="px-2 py-2 text-center font-normal">Cross-attn</th>
                  <th scope="col" className="px-2 py-2 text-center font-normal">Adaptive</th>
                  <th scope="col" className="py-2 pl-4 text-right font-normal">Accuracy</th>
                  <th scope="col" className="py-2 pl-4 pr-1 text-right font-normal">F1</th>
                </tr>
              </thead>
              <tbody className="num divide-y divide-line">
                {ABLATION.map((row) => (
                  <tr key={row.id} className={row.id === "full" ? "bg-leaf-dim/20" : ""}>
                    <th scope="row" className="py-2.5 pl-1 text-left font-normal">
                      <span className={`block ${row.id === "full" ? "font-semibold text-ink" : "text-ink"}`}>{row.name}</span>
                      <span className="block text-xs text-ink-3">{row.description}</span>
                    </th>
                    {row.config ? (
                      <>
                        <td className="py-2.5"><Check on={row.config.scales.length > 1} /></td>
                        <td className="py-2.5"><Check on={row.config.crossAttention} /></td>
                        <td className="py-2.5"><Check on={row.config.fusion === "Adaptive"} /></td>
                      </>
                    ) : (
                      <td colSpan={3} className="py-2.5 text-center text-xs text-ink-3">Base paper network</td>
                    )}
                    <td className="py-2.5 pl-4 text-right font-medium text-ink">{pct(row.accuracy)}</td>
                    <td className="py-2.5 pl-4 pr-1 text-right text-ink-2">{pct(row.f1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-xs leading-relaxed text-ink-3">
              With 128 test images, one image equals 0.78 percentage points, so the A, B and C variants differ by one or two images. Base fusion
              accuracy is from the project summary; its per-metric breakdown isn't in results/.
            </p>
          </div>
        </div>
      </Panel>

      <Panel className="mb-6" title="Training curves" description="Loss per epoch as logged during training (results/training_log_mscaf_*.csv).">
        <TrainingCurves />
      </Panel>

      <Notice tone="info" title="About the test set" className="mb-6">
        {TEST_SET.statement} The test images were never augmented or used for training or checkpoint selection; the best checkpoint was chosen on
        the original validation photos.
      </Notice>

      <section aria-labelledby="figures-heading">
        <h2 id="figures-heading" className="mb-4 text-lg font-semibold">Original research figures</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {RESEARCH_FIGURES.filter((f) => !f.src.includes("gradcam")).map((f) => (
            <Figure key={f.src} src={f.src} alt={f.title} caption={f.title} source={f.source} />
          ))}
        </div>
      </section>
    </>
  );
}
