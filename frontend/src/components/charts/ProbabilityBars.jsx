import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CLASSES } from "../../data/classes";
import ChartTooltip from "../ChartTooltip";
import { formatPercent } from "../ui";

// Softmax probability per class for one image. Zero-based axis, class colours follow the class.
export default function ProbabilityBars({ probabilities, predicted }) {
  const data = CLASSES.map((c) => ({
    id: c.id,
    name: c.label,
    value: (probabilities?.[c.id] ?? 0) * 100,
    raw: probabilities?.[c.id] ?? 0,
    color: c.color
  }));

  return (
    <div>
      <div className="h-[168px]" role="img" aria-label={`Class probabilities: ${data.map((d) => `${d.name} ${formatPercent(d.raw)}`).join(", ")}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 72, bottom: 4, left: 4 }} barCategoryGap={14}>
            <XAxis type="number" domain={[0, 100]} hide />
            <YAxis
              type="category"
              dataKey="name"
              width={128}
              tickLine={false}
              axisLine={false}
              tick={({ x, y, payload }) => (
                <text x={x - 8} y={y} dy={4} textAnchor="end" fill={payload.value && data.find((d) => d.name === payload.value)?.id === predicted ? "var(--color-ink)" : "var(--color-ink-2)"} fontSize={13} fontWeight={data.find((d) => d.name === payload.value)?.id === predicted ? 600 : 400}>
                  {payload.value}
                </text>
              )}
            />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.03)" }}
              content={<ChartTooltip rows={(p) => [{ name: p[0].payload.name, value: formatPercent(p[0].payload.raw, 4), color: p[0].payload.color }]} />}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} background={{ fill: "var(--color-raised)", radius: 4 }} minPointSize={2} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.id} fill={d.color} />
              ))}
              <LabelList
                dataKey="raw"
                position="right"
                formatter={(v) => formatPercent(v)}
                style={{ fill: "var(--color-ink)", fontSize: 13, fontVariantNumeric: "tabular-nums" }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <table className="sr-only">
        <caption>Class probabilities</caption>
        <tbody>
          {data.map((d) => (
            <tr key={d.id}>
              <th scope="row">{d.name}</th>
              <td>{formatPercent(d.raw, 4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
