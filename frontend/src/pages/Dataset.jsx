import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartTooltip from "../components/ChartTooltip";
import { ClassChip, Notice, PageHeader, Panel } from "../components/ui";
import { CLASSES } from "../data/classes";
import { DATASET, TEST_SET } from "../data/research";

const total = (counts) => Object.values(counts).reduce((a, b) => a + b, 0);

export default function Dataset() {
  const factor = DATASET.augmentationFactor;
  const chartData = DATASET.splits.map((s) => ({ split: s.label, ...s.counts }));

  return (
    <>
      <PageHeader
        title="Dataset"
        lead={`MSCAF-Net was trained and evaluated on the ${DATASET.name} dataset: ${DATASET.origin}`}
      />

      <div className="mb-6 grid gap-4 md:grid-cols-3">
        {CLASSES.map((c) => (
          <div key={c.id} className="panel p-5">
            <ClassChip id={c.id} size="lg" />
            <p className="mt-1 text-xs text-ink-3">
              Folder name <code className="text-ink-2">{c.id}</code>, model output {c.index}
            </p>
            <p className="mt-3 text-sm text-ink-2">{c.pathogen}</p>
            <p className="mt-1 text-sm leading-relaxed text-ink-3">{c.signs}</p>
          </div>
        ))}
      </div>

      <div className="mb-6 grid gap-6 lg:grid-cols-5">
        <Panel className="lg:col-span-3" title="Images per split" description="Original images, before augmentation.">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-sm">
              <thead>
                <tr className="border-b border-line text-right text-xs text-ink-3">
                  <th scope="col" className="py-2 text-left font-normal">Split</th>
                  {CLASSES.map((c) => (
                    <th key={c.id} scope="col" className="py-2 font-normal">{c.label}</th>
                  ))}
                  <th scope="col" className="py-2 font-normal">Original</th>
                  <th scope="col" className="py-2 font-normal">After augmentation</th>
                </tr>
              </thead>
              <tbody className="num divide-y divide-line text-right">
                {DATASET.splits.map((s) => (
                  <tr key={s.id}>
                    <th scope="row" className="py-3 text-left font-medium text-ink">{s.label}</th>
                    {CLASSES.map((c) => (
                      <td key={c.id} className="py-3 text-ink-2">{s.counts[c.id]}</td>
                    ))}
                    <td className="py-3 font-medium text-ink">{total(s.counts)}</td>
                    <td className="py-3 text-ink">
                      {s.augmented ? total(s.counts) * factor : <span className="text-ink-2">{total(s.counts)} (unchanged)</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-4 text-xs leading-relaxed text-ink-3">
            Counts follow the public iBean split. Augmented counts are {factor} images per original (the original plus 8 fixed augmentations),
            matching preprocessing/augment_dataset.py.
          </p>
        </Panel>

        <Panel className="lg:col-span-2" title="Class balance" description="Original images per class in each split.">
          <div className="h-[240px]" role="img" aria-label="Grouped bar chart of original images per class for train, validation and test splits">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: -12 }} barGap={2} barCategoryGap="24%">
                <CartesianGrid vertical={false} stroke="var(--color-line)" />
                <XAxis dataKey="split" tick={{ fill: "var(--color-ink-2)", fontSize: 12 }} tickLine={false} axisLine={{ stroke: "var(--color-line)" }} />
                <YAxis tick={{ fill: "var(--color-ink-3)", fontSize: 12 }} tickLine={false} axisLine={false} />
                <Tooltip cursor={{ fill: "rgba(255,255,255,0.03)" }} content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12, color: "var(--color-ink-2)" }} iconType="circle" iconSize={8} />
                {CLASSES.map((c) => (
                  <Bar key={c.id} dataKey={c.id} name={c.label} fill={c.color} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Offline augmentation" description="Applied once to the train and validation images, with fixed parameters.">
          <ul className="grid gap-2 sm:grid-cols-2">
            {DATASET.augmentations.map((a) => (
              <li key={a} className="rounded-lg border border-line bg-raised px-3 py-2 text-sm text-ink-2">{a}</li>
            ))}
          </ul>
          <p className="mt-4 text-sm leading-relaxed text-ink-2">
            Images are resized to 224 × 224 before augmenting, and borders created by rotation or translation are filled by reflection.
          </p>
        </Panel>

        <Panel title="How the splits were used">
          <ul className="space-y-3 text-sm leading-relaxed text-ink-2">
            <li>
              <span className="font-medium text-ink">Training:</span> the {total(DATASET.splits[0].counts) * factor} augmented training images.
            </li>
            <li>
              <span className="font-medium text-ink">Checkpoint selection:</span> the {total(DATASET.splits[1].counts)} original validation photos. The
              augmented copies are near-duplicates and score almost perfectly from the first epoch, so they make a poor selection signal.
            </li>
            <li>
              <span className="font-medium text-ink">Evaluation:</span> the original {TEST_SET.size} test images, never augmented and never seen during
              training or selection.
            </li>
          </ul>
          <Notice tone="info" className="mt-4">
            {TEST_SET.statement}
          </Notice>
        </Panel>
      </div>
    </>
  );
}
