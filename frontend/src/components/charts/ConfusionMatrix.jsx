import { CLASSES } from "../../data/classes";

// Rows = true class, columns = predicted class. Diagonal cells use a single
// leaf ramp by row share; off-diagonal errors are outlined and labelled.
export default function ConfusionMatrix({ matrix, compact = false }) {
  return (
    <div className="overflow-x-auto">
      <table className={`w-full ${compact ? "min-w-[300px]" : "min-w-[420px]"} border-separate border-spacing-1.5 text-sm`}>
        <caption className="sr-only">Confusion matrix: rows are true classes, columns are predicted classes</caption>
        <thead>
          <tr>
            <th scope="col" className="w-36 text-left text-xs font-normal text-ink-3">True \ Predicted</th>
            {CLASSES.map((c) => (
              <th key={c.id} scope="col" className="px-1 pb-1 text-center text-xs font-medium text-ink-2">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => {
            const total = row.reduce((a, b) => a + b, 0);
            return (
              <tr key={CLASSES[i].id}>
                <th scope="row" className="pr-2 text-left text-xs font-medium text-ink-2">
                  {CLASSES[i].label}
                  <span className="block font-normal text-ink-3">n = {total}</span>
                </th>
                {row.map((count, j) => {
                  const share = total ? count / total : 0;
                  const diagonal = i === j;
                  const error = !diagonal && count > 0;
                  const style = diagonal
                    ? { background: `color-mix(in oklab, var(--color-leaf) ${Math.round(18 + share * 52)}%, var(--color-panel))` }
                    : undefined;
                  return (
                    <td
                      key={j}
                      title={`${count} ${CLASSES[i].label.toLowerCase()} image${count === 1 ? "" : "s"} predicted as ${CLASSES[j].label.toLowerCase()}`}
                      className={`rounded-lg text-center align-middle ${compact ? "h-14" : "h-20"} ${
                        diagonal ? "text-ink" : error ? "border border-amber bg-amber-dim/40 text-ink" : "bg-raised text-ink-3"
                      }`}
                      style={style}
                    >
                      <span className={`num block font-display ${compact ? "text-xl" : "text-2xl"} font-semibold`}>{count}</span>
                      {!compact && (count > 0 || diagonal) && (
                        <span className="num block text-xs text-ink-2">{(share * 100).toFixed(1)}%</span>
                      )}
                      {error && <span className="sr-only">misclassified</span>}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
