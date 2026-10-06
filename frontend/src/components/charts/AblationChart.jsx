import { CartesianGrid, LabelList, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from "recharts";
import { ABLATION } from "../../data/research";
import ChartTooltip from "../ChartTooltip";

// Dot plot: accuracy differences are a few points near 100%, so a dot plot
// with a truncated axis is honest where truncated bars would not be.
export default function AblationChart({ height = 260, compact = false }) {
  const data = ABLATION.map((row) => ({ ...row, label: compact ? row.name.replace("MSCAF-", "") : row.name }));

  const Dot = ({ cx, cy, payload }) => {
    const full = payload.id === "full";
    const base = payload.id === "base";
    return (
      <g>
        <circle
          cx={cx}
          cy={cy}
          r={full ? 8 : 6}
          fill={full ? "var(--color-leaf)" : base ? "var(--color-panel)" : "var(--color-ink-3)"}
          stroke={full ? "var(--color-panel)" : base ? "var(--color-ink-2)" : "var(--color-panel)"}
          strokeWidth={2}
        />
      </g>
    );
  };

  return (
    <div>
      <div style={{ height }} role="img" aria-label={`Ablation test accuracy: ${ABLATION.map((r) => `${r.name} ${r.accuracy}%`).join(", ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 56, bottom: 8, left: 4 }}>
            <CartesianGrid horizontal={false} stroke="var(--color-line)" strokeDasharray="0" />
            <XAxis
              type="number"
              dataKey="accuracy"
              domain={[96, 100]}
              ticks={[96, 97, 98, 99, 100]}
              tickFormatter={(v) => `${v}%`}
              tick={{ fill: "var(--color-ink-3)", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "var(--color-line)" }}
            />
            <YAxis
              type="category"
              dataKey="label"
              allowDuplicatedCategory={false}
              reversed
              width={compact ? 48 : 104}
              tick={{ fill: "var(--color-ink-2)", fontSize: 13 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={false}
              content={
                <ChartTooltip
                  rows={(p) => {
                    const r = p[0].payload;
                    return [
                      { name: r.name, value: `${r.accuracy.toFixed(2)}%` },
                      { name: r.description, value: "" }
                    ];
                  }}
                />
              }
            />
            <Scatter data={data} shape={<Dot />} isAnimationActive={false}>
              <LabelList dataKey="accuracy" position="right" offset={12} formatter={(v) => `${v.toFixed(2)}%`} style={{ fill: "var(--color-ink)", fontSize: 13, fontVariantNumeric: "tabular-nums" }} />
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-3">
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-leaf" aria-hidden />Full MSCAF-Net</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full bg-ink-3" aria-hidden />Ablation variant</span>
        <span className="inline-flex items-center gap-1.5"><span className="size-2.5 rounded-full border border-ink-2" aria-hidden />Base fusion network</span>
        <span>Axis starts at 96%</span>
      </div>
    </div>
  );
}
