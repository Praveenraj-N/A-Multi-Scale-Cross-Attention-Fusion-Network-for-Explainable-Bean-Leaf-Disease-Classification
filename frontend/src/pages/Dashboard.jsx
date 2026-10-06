import { Link, useOutletContext } from "react-router";
import { ArrowRight, Boxes, CircleCheck, Cpu, Layers, RefreshCw, ScanEye, ScanLine, Trash2 } from "lucide-react";
import { ClassChip, KeyValueList, Panel, PageHeader, formatPercent } from "../components/ui";
import StatTile from "../components/StatTile";
import StatusBadge from "../components/StatusBadge";
import AblationChart from "../components/charts/AblationChart";
import { CLASS_REPORT, FULL_MODEL_METRICS, MODEL_CONFIG, TEST_SET } from "../data/research";
import { CLASSES } from "../data/classes";
import { useAnalysis } from "../context/AnalysisContext";

function MetricsSection() {
  const m = FULL_MODEL_METRICS;
  const metrics = [
    { label: "Accuracy", value: `${m.accuracy.toFixed(2)}%`, emphasis: true },
    { label: "Precision", value: `${m.precision.toFixed(2)}%` },
    { label: "Recall", value: `${m.recall.toFixed(2)}%` },
    { label: "F1 score", value: `${m.f1.toFixed(2)}%` }
  ];

  return (
    <section aria-labelledby="metrics-heading" className="mb-6">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="metrics-heading" className="text-lg font-semibold">Research results on the test set</h2>
        <p className="text-sm text-ink-3">{TEST_SET.statement} Precision, recall and F1 are weighted averages.</p>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {metrics.map((metric) => (
          <StatTile key={metric.label} label={metric.label} value={metric.value} emphasis={metric.emphasis} icon={metric.emphasis ? CircleCheck : undefined} />
        ))}
      </div>
      <p className="mt-3 text-xs text-ink-3">
        These describe the model across all 128 test images. They are not the confidence of any single prediction.
      </p>
    </section>
  );
}

function FactsRow({ health }) {
  const gpuReady = health.status === "ready" && health.data?.device === "cuda";
  const modelValue = {
    ready: gpuReady ? "GPU ready" : "CPU ready",
    loading: "Loading",
    offline: "Offline",
    checking: "Checking",
    mock: "Mock mode"
  }[health.status];

  return (
    <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
      <StatTile label="Test images correct" value={`${FULL_MODEL_METRICS.correct} / ${FULL_MODEL_METRICS.total}`} note="One misclassification" icon={CircleCheck} />
      <StatTile label="Disease classes" value="3" note="Angular leaf spot, bean rust, healthy" icon={Layers} />
      <StatTile label="Parameters" value={`${MODEL_CONFIG.parametersM}M`} note="Full MSCAF-Net" icon={Boxes} />
      <StatTile label="Explainability" value="Grad-CAM" note="Enabled on every prediction" icon={ScanEye} tone="xai" />
      <StatTile
        label="Model status"
        value={modelValue}
        note={health.data?.gpu_name ?? (health.status === "offline" ? "Start the FastAPI backend" : "Live from /health")}
        icon={Cpu}
        tone={health.status === "ready" ? "leaf" : health.status === "offline" ? "muted" : "amber"}
      />
    </div>
  );
}

function StatusPanel({ health }) {
  return (
    <Panel
      title="Model status"
      description="Checked live against the FastAPI backend every 30 seconds."
      action={
        <button type="button" onClick={health.refresh} className="rounded-lg p-2 text-ink-3 hover:bg-raised hover:text-ink" aria-label="Refresh status">
          <RefreshCw className="size-4" />
        </button>
      }
    >
      <div className="mb-4">
        <StatusBadge health={health} />
      </div>
      {health.status === "offline" && (
        <p className="mb-4 text-sm leading-relaxed text-ink-3">
          Start it from the project root with{" "}
          <code className="rounded bg-raised px-1.5 py-0.5 text-xs text-ink-2">.venv\Scripts\python -m uvicorn backend.app.main:app --port 8000</code>
        </p>
      )}
      <KeyValueList
        items={[
          { label: "Device", value: health.data?.device?.toUpperCase() ?? "—" },
          { label: "GPU", value: health.data?.gpu_name ?? "—" },
          { label: "Checkpoint", value: "baseline_mscaf_full_best.pth" },
          { label: "Checkpoint epoch", value: MODEL_CONFIG.checkpointEpoch }
        ]}
      />
    </Panel>
  );
}

function ConfigPanel() {
  const c = MODEL_CONFIG;
  return (
    <Panel title="Model configuration" description="Stored in the trained checkpoint.">
      <KeyValueList
        items={[
          { label: "Fusion scales", value: c.scales.map((s) => `${s}×${s}`).join(", ") },
          { label: "Embedding dimension", value: c.dim },
          { label: "Attention heads", value: c.heads },
          { label: "Cross-attention", value: c.crossAttention ? "Enabled" : "Disabled" },
          { label: "Fusion", value: c.fusion },
          { label: "Dropout", value: c.dropout },
          { label: "Input size", value: `${c.inputSize} × ${c.inputSize}` }
        ]}
      />
    </Panel>
  );
}

function ClassResultsPanel() {
  return (
    <Panel title="Results by class" description="Correct test images per class for the full model.">
      <ul className="space-y-4">
        {CLASS_REPORT.map((row) => {
          const correct = Math.round(row.recall * row.support);
          return (
            <li key={row.id}>
              <div className="mb-1.5 flex items-baseline justify-between gap-3">
                <ClassChip id={row.id} />
                <span className="num text-sm text-ink">
                  {correct} / {row.support}
                  <span className="ml-2 text-ink-3">recall {(row.recall * 100).toFixed(2)}%</span>
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-raised" aria-hidden>
                <div className="h-full rounded-full" style={{ width: `${row.recall * 100}%`, background: CLASSES.find((c) => c.id === row.id).color }} />
              </div>
            </li>
          );
        })}
      </ul>
      <Link to="/results" className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-leaf hover:underline">
        Full results and confusion matrix <ArrowRight className="size-3.5" aria-hidden />
      </Link>
    </Panel>
  );
}

function RecentPanel() {
  const { history, clearHistory } = useAnalysis();

  return (
    <Panel
      title="Recent analyses"
      description="Leaf photos analyzed in this browser."
      action={
        history.length > 0 && (
          <button type="button" onClick={clearHistory} className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-ink-3 hover:bg-raised hover:text-ink">
            <Trash2 className="size-3.5" aria-hidden /> Clear
          </button>
        )
      }
    >
      {history.length === 0 ? (
        <div className="flex flex-col items-start gap-3 rounded-xl border border-dashed border-line-strong p-5">
          <p className="text-sm text-ink-2">No leaves analyzed yet. Upload a photo to see the prediction and its Grad-CAM explanation here.</p>
          <Link to="/predict" className="inline-flex items-center gap-2 rounded-lg bg-leaf px-3.5 py-2 text-sm font-semibold text-ground hover:bg-leaf/90">
            <ScanLine className="size-4" aria-hidden /> Analyze a leaf
          </Link>
        </div>
      ) : (
        <ul className="divide-y divide-line">
          {history.map((item) => (
            <li key={item.id} className="flex items-center gap-3 py-2.5">
              {item.thumb ? (
                <img src={item.thumb} alt="" className="size-11 shrink-0 rounded-lg object-cover" />
              ) : (
                <div className="size-11 shrink-0 rounded-lg bg-raised" />
              )}
              <div className="min-w-0 flex-1">
                <ClassChip id={item.predictedClass} />
                <p className="truncate text-xs text-ink-3">
                  {item.fileName} {item.isMock && <span className="text-amber">(mock data)</span>}
                </p>
              </div>
              <div className="text-right">
                <p className="num text-sm font-medium text-ink">{formatPercent(item.confidence)}</p>
                <p className="text-xs text-ink-3">
                  {new Date(item.analyzedAt).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export default function Dashboard() {
  const { health } = useOutletContext();

  return (
    <>
      <PageHeader
        title="MSCAF-Net"
        lead="Multi-Scale Cross-Attention Fusion Network for explainable bean leaf disease classification. Upload a leaf photo for a diagnosis with a Grad-CAM explanation, or explore how the model was built and evaluated."
        actions={
          <>
            <Link to="/predict" className="inline-flex items-center gap-2 rounded-xl bg-leaf px-4 py-2.5 text-sm font-semibold text-ground shadow-[0_0_24px_-6px_var(--color-leaf)] hover:bg-leaf/90">
              <ScanLine className="size-4" aria-hidden /> Analyze a leaf
            </Link>
            <Link to="/results" className="inline-flex items-center gap-2 rounded-xl border border-line-strong px-4 py-2.5 text-sm font-medium text-ink hover:bg-raised">
              View research results
            </Link>
          </>
        }
      />

      <MetricsSection />
      <FactsRow health={health} />

      <div className="mb-6 grid gap-6 lg:grid-cols-3">
        <Panel
          className="lg:col-span-2"
          title="Ablation study"
          description="Test accuracy as each MSCAF-Net component is added, against the base fusion network."
          action={
            <Link to="/results" className="hidden shrink-0 items-center gap-1.5 text-sm font-medium text-leaf hover:underline sm:inline-flex">
              Details <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          }
        >
          <AblationChart height={250} />
        </Panel>
        <StatusPanel health={health} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <ConfigPanel />
        <ClassResultsPanel />
        <RecentPanel />
      </div>
    </>
  );
}
