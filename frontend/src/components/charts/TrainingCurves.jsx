import { useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { trainingLog } from "../../data/trainingLog";
import { ABLATION } from "../../data/research";
import ChartTooltip from "../ChartTooltip";

const SERIES = [
  { key: "trainLoss", name: "Training loss", color: "#9fb3aa", dash: "5 4" },
  { key: "valLoss", name: "Validation loss", color: "var(--color-leaf)", dash: undefined }
];

const VARIANTS = [
  { id: "full", label: "Full" },
  { id: "A", label: "A" },
  { id: "B", label: "B" },
  { id: "C", label: "C" }
];

export default function TrainingCurves() {
  const [variant, setVariant] = useState("full");
  const data = trainingLog[variant];
  const bestEpoch = ABLATION.find((a) => a.id === variant)?.epoch;

  const [minTick, ticks] = useMemo(() => {
    const min = Math.min(...data.flatMap((d) => [d.trainLoss, d.valLoss]).filter((v) => v > 0));
    const low = Math.pow(10, Math.floor(Math.log10(min)));
    const t = [];
    for (let v = low; v <= 1.0001; v *= 10) t.push(Number(v.toPrecision(1)));
    return [low, t];
  }, [data]);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-lg border border-line bg-ground p-0.5" role="group" aria-label="Model variant">
          {VARIANTS.map((v) => (
            <button
              key={v.id}
              type="button"
              onClick={() => setVariant(v.id)}
              aria-pressed={variant === v.id}
              className={`rounded-md px-3 py-1.5 text-sm transition-colors ${variant === v.id ? "bg-raised text-ink" : "text-ink-3 hover:text-ink-2"}`}
            >
              {v.id === "full" ? "MSCAF-Full" : `MSCAF-${v.label}`}
            </button>
          ))}
        </div>
        <p className="text-xs text-ink-3">Log scale. Dashed vertical line marks the saved best checkpoint.</p>
      </div>

      <div className="h-[280px]" role="img" aria-label={`Training and validation loss over 50 epochs for MSCAF-${variant}; best checkpoint at epoch ${bestEpoch}`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--color-line)" />
            <XAxis
              dataKey="epoch"
              type="number"
              domain={[1, 50]}
              ticks={[1, 10, 20, 30, 40, 50]}
              tick={{ fill: "var(--color-ink-3)", fontSize: 12 }}
              tickLine={false}
              axisLine={{ stroke: "var(--color-line)" }}
              label={{ value: "Epoch", position: "insideBottomRight", offset: -2, fill: "var(--color-ink-3)", fontSize: 12 }}
            />
            <YAxis
              scale="log"
              domain={[minTick, 1]}
              ticks={ticks}
              allowDataOverflow
              tickFormatter={(v) => (v >= 0.01 ? v : v.toExponential(0))}
              tick={{ fill: "var(--color-ink-3)", fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={52}
            />
            <Tooltip
              cursor={{ stroke: "var(--color-line-strong)" }}
              content={<ChartTooltip labelFormat={(l) => `Epoch ${l}`} format={(v) => v.toExponential(2)} />}
            />
            <Legend iconType="plainline" wrapperStyle={{ fontSize: 12, color: "var(--color-ink-2)", paddingTop: 8 }} />
            {bestEpoch && (
              <ReferenceLine
                x={bestEpoch}
                stroke="var(--color-ink-3)"
                strokeDasharray="3 3"
                label={{ value: `Best checkpoint, epoch ${bestEpoch}`, position: "insideTopLeft", fill: "var(--color-ink-2)", fontSize: 11 }}
              />
            )}
            {SERIES.map((s) => (
              <Line
                key={s.key}
                dataKey={s.key}
                name={s.name}
                stroke={s.color}
                strokeWidth={2}
                strokeDasharray={s.dash}
                dot={false}
                activeDot={{ r: 4, stroke: "var(--color-panel)", strokeWidth: 2 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
