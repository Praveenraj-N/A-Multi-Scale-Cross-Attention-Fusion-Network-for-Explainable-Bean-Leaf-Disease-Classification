import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { ArrowRight, Clock, Cpu, LoaderCircle, MapPinned, RotateCcw, ScanLine } from "lucide-react";
import ImageDropzone from "../components/ImageDropzone";
import CompareSlider from "../components/CompareSlider";
import ProbabilityBars from "../components/charts/ProbabilityBars";
import ScaleContribution from "../components/charts/ScaleContribution";
import { ImageTile, KeyValueList, Notice, PageHeader, Panel, formatPercent } from "../components/ui";
import { useAnalysis } from "../context/AnalysisContext";
import { classColor, classLabel } from "../data/classes";
import { MOCK_IMAGES } from "../data/mockPrediction";
import { API_BASE_URL, USE_MOCK, predictImage, validateImageFile } from "../services/api";

const LOW_CONFIDENCE = 0.7;

function ConfidenceBlock({ result }) {
  const pct = result.confidence * 100;
  return (
    <div>
      <p className="text-sm text-ink-2">Prediction confidence</p>
      <p className="num mt-1 font-display text-5xl font-semibold leading-none text-ink">{formatPercent(result.confidence)}</p>
      <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-raised" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Number(pct.toFixed(2))} aria-label="Prediction confidence">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: classColor(result.predicted_class) }} />
      </div>
      <p className="mt-3 text-xs leading-relaxed text-ink-3">
        The model's softmax probability for this image. It is separate from the 99.22% test-set accuracy, which describes performance over 128
        test images.
      </p>
    </div>
  );
}

function AnalyzingState({ previewUrl }) {
  return (
    <Panel>
      <div className="grid items-center gap-6 md:grid-cols-[220px_1fr]">
        <div className="relative aspect-square overflow-hidden rounded-xl border border-line bg-raised">
          {previewUrl && <img src={previewUrl} alt="Leaf being analyzed" className="size-full object-cover opacity-80" />}
          <div className="absolute inset-0 overflow-hidden" aria-hidden>
            <div className="scan-line h-full w-full bg-gradient-to-b from-transparent via-xai/25 to-transparent" />
          </div>
        </div>
        <div role="status" aria-live="polite">
          <p className="flex items-center gap-2 font-display text-xl font-semibold text-ink">
            <LoaderCircle className="size-5 animate-spin text-xai" aria-hidden /> Analyzing the leaf
          </p>
          <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-2">
            Running MSCAF-Net on the image, then computing the Grad-CAM heatmap for the predicted class. This usually takes under a second on
            the GPU.
          </p>
        </div>
      </div>
    </Panel>
  );
}

function ResultView({ analysis }) {
  const { result, imageUrl, fileName } = analysis;
  const gradcam = result.gradcam;
  const gradcamOk = gradcam?.status === "success";
  const p = result.processing;

  return (
    <div className="space-y-6">
      {result.isMock && (
        <Notice tone="mock" title="Mock data">
          This result is replayed sample data for UI development (VITE_USE_MOCK=true). It was not produced from your uploaded image.
        </Notice>
      )}

      <div className="grid gap-6 lg:grid-cols-12">
        <Panel className="lg:col-span-5" title="Original image" description={fileName}>
          <div className="aspect-square overflow-hidden rounded-xl border border-line bg-ground">
            <img src={imageUrl} alt={`Uploaded leaf: ${fileName}`} className="size-full object-contain" />
          </div>
        </Panel>

        <Panel className="lg:col-span-7" title="Prediction">
          <div className="grid gap-8 md:grid-cols-2">
            <div>
              <p className="text-sm text-ink-2">Predicted disease</p>
              <p className="mt-2 font-display text-[2rem] font-semibold leading-tight" style={{ color: "var(--color-ink)" }}>
                <span className="mr-2.5 inline-block size-3.5 rounded-full align-middle" style={{ background: classColor(result.predicted_class) }} aria-hidden />
                {classLabel(result.predicted_class)}
              </p>
              <p className="mt-2 text-sm text-ink-3">
                {result.predicted_class === "healthy" ? "No signs of angular leaf spot or bean rust were predicted." : "Fungal leaf disease predicted."}
              </p>
            </div>
            <ConfidenceBlock result={result} />
          </div>

          {result.confidence < LOW_CONFIDENCE && (
            <Notice tone="warn" title="Low confidence" className="mt-6">
              The model isn't confident about this image. Retake the photo with one leaf filling the frame in even daylight, or have it checked by
              an expert.
            </Notice>
          )}

          <div className="mt-6 border-t border-line pt-5">
            <h3 className="mb-3 text-[15px] font-semibold text-ink">Class probabilities</h3>
            <ProbabilityBars probabilities={result.class_probabilities} predicted={result.predicted_class} />
          </div>

          {!result.isMock && (
            <div className="mt-5 border-t border-line pt-5">
              <Link
                to="/outbreak"
                state={{ prefill: { disease: result.predicted_class, confidence: result.confidence } }}
                className="inline-flex items-center gap-2 text-sm font-medium text-xai hover:underline"
              >
                <MapPinned className="size-4" aria-hidden /> Report this detection to Outbreak Monitoring
              </Link>
              <p className="mt-1 text-xs text-ink-3">Opens a form pre-filled with this prediction. You add the location; it is saved as an unverified model detection.</p>
            </div>
          )}
        </Panel>
      </div>

      <Panel
        title="Grad-CAM explanation"
        description={`Regions that influenced the ${classLabel(gradcam?.target_class ?? result.predicted_class).toLowerCase()} prediction, from the fused 7×7 representation (layer ${gradcam?.target_layer ?? "fusion_identity"}).`}
        action={
          <Link to="/explainability" className="hidden shrink-0 items-center gap-1.5 text-sm font-medium text-xai hover:underline sm:inline-flex">
            How to read this <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        }
      >
        {gradcamOk ? (
          <div className="grid gap-6 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
            <div>
              <CompareSlider before={imageUrl} after={gradcam.overlay_url} beforeLabel="Leaf" afterLabel="Grad-CAM overlay" />
              <p className="mt-2 text-xs text-ink-3">Drag across the image, or focus it and use the arrow keys. Shown at the model's square 224 × 224 input.</p>
            </div>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-1 xl:grid-cols-2">
              <ImageTile src={gradcam.heatmap_url} alt="Grad-CAM heatmap" label="Heatmap" note="Red = stronger influence, blue = weaker" fit="fill" />
              <ImageTile src={gradcam.overlay_url} alt="Grad-CAM overlay on the leaf" label="Overlay" note="Heatmap blended at 40% over the input" fit="fill" />
            </div>
          </div>
        ) : (
          <Notice tone={gradcam ? "warn" : "info"} title={gradcam ? "Grad-CAM couldn't be generated" : "Grad-CAM was turned off for this analysis"}>
            {gradcam?.error ?? "Turn on Grad-CAM before analyzing to see which regions influenced the prediction."}
          </Notice>
        )}
        <p className="mt-5 text-sm leading-relaxed text-ink-2">
          Grad-CAM provides a qualitative visualization of spatial regions that influenced the model's prediction. It is not a disease
          segmentation and doesn't prove that a highlighted region caused the result.
        </p>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Adaptive scale contribution" description="How the final fusion layer weighted the three feature scales for this image.">
          <ScaleContribution weights={result.scale_fusion_weights} />
        </Panel>

        <Panel title="Processing" description={result.isMock ? "Values from the mock sample." : "Reported by the API for this request."}>
          <KeyValueList
            items={[
              { label: "Device", value: p.device === "cuda" ? "CUDA GPU" : p.device.toUpperCase() },
              { label: "Model inference", value: `${p.inference_ms.toFixed(1)} ms` },
              { label: "Grad-CAM", value: p.gradcam_ms != null ? `${p.gradcam_ms.toFixed(1)} ms` : "Not run" },
              { label: "Total server time", value: `${p.total_ms.toFixed(1)} ms` },
              { label: "Original size", value: `${p.original_size[0]} × ${p.original_size[1]} px` },
              { label: "Model input", value: `${p.input_size[0]} × ${p.input_size[1]} px` },
              { label: "File", value: p.filename ?? fileName }
            ]}
          />
        </Panel>
      </div>
    </div>
  );
}

export default function Predict() {
  const { current, recordAnalysis } = useAnalysis();
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [withGradcam, setWithGradcam] = useState(true);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const abortRef = useRef(null);
  const handedOff = useRef(new Set());

  // Revoke preview URLs that were never handed to the analysis context
  useEffect(() => {
    const url = previewUrl;
    return () => {
      if (url && !handedOff.current.has(url)) URL.revokeObjectURL(url);
    };
  }, [previewUrl]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const selectFile = (next) => {
    const problem = validateImageFile(next);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setFile(next);
    setPreviewUrl(URL.createObjectURL(next));
  };

  const clearFile = () => {
    setFile(null);
    setPreviewUrl(null);
    setError(null);
  };

  const analyze = async () => {
    if (!file) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setStatus("loading");
    setError(null);

    try {
      const result = await predictImage(file, { gradcam: withGradcam, signal: controller.signal });
      const imageUrl = result.isMock ? MOCK_IMAGES.original : previewUrl;
      if (!result.isMock) handedOff.current.add(previewUrl);
      await recordAnalysis({ result, imageUrl, fileName: file.name });
      setStatus("done");
      setFile(null);
      setPreviewUrl(null);
    } catch (err) {
      if (err.name === "AbortError") return;
      setError(err.message);
      setStatus("error");
    }
  };

  const loading = status === "loading";

  return (
    <>
      <PageHeader
        title="Disease Prediction"
        lead="Upload a photo of a bean leaf. MSCAF-Net classifies it as angular leaf spot, bean rust or healthy, and Grad-CAM shows which image regions influenced the prediction."
      />

      <Panel className="mb-6" bodyClassName="p-5 sm:p-6">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
          <ImageDropzone file={file} previewUrl={previewUrl} onSelect={selectFile} onClear={clearFile} disabled={loading} />

          <div className="flex flex-col justify-between gap-5 rounded-xl border border-line bg-ground/40 p-4">
            <div className="space-y-4">
              <label className="flex cursor-pointer items-start gap-3">
                <input
                  type="checkbox"
                  checked={withGradcam}
                  onChange={(e) => setWithGradcam(e.target.checked)}
                  className="mt-0.5 size-4 accent-[var(--color-xai)]"
                  disabled={loading}
                />
                <span>
                  <span className="block text-sm font-medium text-ink">Generate Grad-CAM</span>
                  <span className="block text-xs leading-relaxed text-ink-3">Adds the heatmap and overlay. Takes a little longer.</span>
                </span>
              </label>
              <div className="space-y-1.5 text-xs text-ink-3">
                <p className="flex items-center gap-2">
                  <Cpu className="size-3.5" aria-hidden /> {USE_MOCK ? "Mock mode, no API calls" : `API: ${API_BASE_URL}`}
                </p>
                <p className="flex items-center gap-2">
                  <Clock className="size-3.5" aria-hidden /> Images are processed in memory and not stored.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={analyze}
              disabled={!file || loading}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-leaf px-4 py-3 text-sm font-semibold text-ground transition-colors hover:bg-leaf/90 disabled:cursor-not-allowed disabled:bg-raised disabled:text-ink-3"
            >
              {loading ? <LoaderCircle className="size-4 animate-spin" aria-hidden /> : <ScanLine className="size-4" aria-hidden />}
              {loading ? "Analyzing" : "Analyze leaf"}
            </button>
          </div>
        </div>

        {error && (
          <Notice tone="error" title={status === "error" ? "Analysis failed" : "Can't use this file"} className="mt-5">
            {error}
          </Notice>
        )}
      </Panel>

      {loading && <AnalyzingState previewUrl={previewUrl} />}

      {!loading && current && (
        <>
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-xl font-semibold">
              Latest result <span className="font-sans text-sm font-normal text-ink-3">{new Date(current.analyzedAt).toLocaleTimeString()}</span>
            </h2>
            {file === null && (
              <p className="flex items-center gap-1.5 text-sm text-ink-3">
                <RotateCcw className="size-3.5" aria-hidden /> Upload another image above to run a new analysis.
              </p>
            )}
          </div>
          <ResultView analysis={current} />
        </>
      )}

      {!loading && !current && (
        <div className="grid gap-4 rounded-2xl border border-dashed border-line-strong p-6 text-sm text-ink-2 md:grid-cols-3">
          {[
            ["Prediction and confidence", "The most likely class and the model's probability for each of the three classes."],
            ["Grad-CAM heatmap", "A qualitative map of which regions influenced the prediction, with a slider to compare it against the leaf."],
            ["Scale contribution", "How much the 28×28, 14×14 and 7×7 feature scales each contributed to the decision."]
          ].map(([title, text]) => (
            <div key={title}>
              <p className="font-medium text-ink">{title}</p>
              <p className="mt-1 leading-relaxed text-ink-3">{text}</p>
            </div>
          ))}
          <p className="text-xs text-ink-3 md:col-span-3">
            The model always answers with one of its three classes, so photos of other plants or objects will still get a label. Only use it on
            bean leaves.
          </p>
        </div>
      )}
    </>
  );
}
