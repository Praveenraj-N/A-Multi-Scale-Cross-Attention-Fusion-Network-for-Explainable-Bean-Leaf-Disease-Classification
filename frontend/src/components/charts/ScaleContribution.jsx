import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartTooltip from "../ChartTooltip";

// Ordinal teal steps: fine scale (28) light -> coarse scale (7) dark.
const SCALE_STEPS = {
  "28x28": "#7fd6d3",
  "14x14": "#2bb3b1",
  "7x7": "#1b7f7d"
};

const SCALE_LABEL = {
  "28x28": "28 × 28 (fine detail)",
  "14x14": "14 × 14 (mid-level)",
  "7x7": "7 × 7 (global context)"
};

export default function ScaleContribution({ weights }) {
  if (!weights) return <p className="text-sm text-ink-3">Scale weights were not returned for this image.</p>;

  const data = Object.entries(weights).map(([key, value]) => ({
    key,
    name: SCALE_LABEL[key] ?? key,
    value: value * 100,
    color: SCALE_STEPS[key] ?? "var(--color-xai)"
  }));

  const max = Math.max(50, Math.ceil(Math.max(...data.map((d) => d.value)) / 10) * 10);

  return (
    <div>
      <div className="h-[150px]" role="img" aria-label={`Adaptive scale contribution: ${data.map((d) => `${d.name} ${d.value.toFixed(1)}%`).join(", ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, bottom: 4, left: 4 }} barCategoryGap={12}>
            <XAxis type="number" domain={[0, max]} hide />
            <YAxis type="category" dataKey="name" width={150} tickLine={false} axisLine={false} tick={{ fill: "var(--color-ink-2)", fontSize: 13 }} />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.03)" }}
              content={<ChartTooltip rows={(p) => [{ name: p[0].payload.name, value: `${p[0].payload.value.toFixed(2)}%`, color: p[0].payload.color }]} />}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.key} fill={d.color} />
              ))}
              <LabelList dataKey="value" position="right" formatter={(v) => `${v.toFixed(1)}%`} style={{ fill: "var(--color-ink)", fontSize: 13 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-3 text-xs leading-relaxed text-ink-3">
        Weights of the final adaptive fusion layer for this image, averaged over the 128 feature channels. They sum to 100% and show how much
        each scale contributed to the fused feature vector, not where the disease is.
      </p>
    </div>
  );
}
