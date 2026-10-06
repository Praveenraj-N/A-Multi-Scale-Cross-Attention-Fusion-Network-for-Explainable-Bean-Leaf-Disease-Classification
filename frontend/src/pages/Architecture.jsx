import ArchitectureDiagram from "../components/ArchitectureDiagram";
import { KeyValueList, PageHeader, Panel } from "../components/ui";
import { MODEL_CONFIG } from "../data/research";

const COMPONENTS = [
  {
    title: "PVT v2-B2 branch",
    tone: "border-xai/40",
    text: "A pyramid vision transformer (timm pvt_v2_b2) whose attention spans the whole image, so it captures leaf shape and the overall spread of symptoms. Its 28×28, 14×14 and 7×7 stage outputs are used."
  },
  {
    title: "GCADSN branch",
    tone: "border-leaf/40",
    text: "A compact CNN built from group convolution, channel shuffle and depthwise-separable convolution blocks, ending in a four-branch global context block. It focuses on local texture such as lesion edges and rust pustules."
  },
  {
    title: "Multi-scale fusion",
    tone: "border-line-strong",
    text: "Instead of fusing only the last feature map, both branches are fused at three resolutions: 28×28 for fine detail, 14×14 for mid-level patterns and 7×7 for global context. Each map is first projected to 128 channels."
  },
  {
    title: "Bidirectional cross-attention",
    tone: "border-line-strong",
    text: "At every scale, PVT features query GCADSN features and GCADSN features query PVT features (4 heads, learned 2D position embeddings). Output projections start at zero, so each block begins as an identity and learns how much to attend."
  },
  {
    title: "Adaptive fusion",
    tone: "border-line-strong",
    text: "Small gating networks produce per-image, per-channel softmax weights. One gate per scale balances the two branches; a final gate balances the three scales. These are the scale weights shown with every prediction."
  },
  {
    title: "Classifier",
    tone: "border-line-strong",
    text: "The fused 128-dimensional vector passes through dropout (0.1) and a single linear layer that outputs scores for the three classes."
  }
];

export default function Architecture() {
  const c = MODEL_CONFIG;

  return (
    <>
      <PageHeader
        title="Model Architecture"
        lead="MSCAF-Net combines a transformer branch and a CNN branch, fuses them at three scales with bidirectional cross-attention, and lets learned gates decide how much each branch and scale contributes."
      />

      <Panel className="mb-6" bodyClassName="p-5 sm:p-8">
        <ArchitectureDiagram />
        <p className="mx-auto mt-6 max-w-2xl text-center text-xs leading-relaxed text-ink-3">
          Global average pooling is applied to each scale's fused map before the multi-scale fusion, as implemented in models/mscaf_net.py. The
          7×7 fused map is wrapped by the fusion_identity layer used for Grad-CAM.
        </p>
      </Panel>

      <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {COMPONENTS.map((item) => (
          <div key={item.title} className={`panel border-l-2 p-5 ${item.tone}`}>
            <h2 className="text-[17px] font-semibold text-ink">{item.title}</h2>
            <p className="mt-2 text-sm leading-relaxed text-ink-2">{item.text}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Configuration" description="Read from the checkpoint's stored model_config.">
          <KeyValueList
            items={[
              { label: "Fusion scales", value: c.scales.map((s) => `${s}×${s}`).join(", ") },
              { label: "Embedding dimension", value: c.dim },
              { label: "Attention heads", value: c.heads },
              { label: "Cross-attention", value: "Enabled, bidirectional" },
              { label: "Fusion", value: "Adaptive (branch and scale gates)" },
              { label: "Dropout", value: c.dropout },
              { label: "Parameters", value: `${c.parametersM}M` }
            ]}
          />
        </Panel>
        <Panel title="Feature maps per scale" description="Channels before the 1×1 projection to 128.">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-ink-3">
                  <th scope="col" className="py-2 font-normal">Scale</th>
                  <th scope="col" className="py-2 font-normal">PVT v2 source</th>
                  <th scope="col" className="py-2 font-normal">GCADSN source</th>
                </tr>
              </thead>
              <tbody className="num divide-y divide-line">
                {[
                  ["28 × 28", "Stage 2, 128 ch", "GSDW block 1, 9 ch"],
                  ["14 × 14", "Stage 3, 320 ch", "GSDW block 2, 12 ch"],
                  ["7 × 7", "Stage 4, 512 ch", "Global context block, 48 ch"]
                ].map(([scale, pvt, cnn]) => (
                  <tr key={scale}>
                    <th scope="row" className="py-2.5 text-left font-medium text-ink">{scale}</th>
                    <td className="py-2.5 text-ink-2">{pvt}</td>
                    <td className="py-2.5 text-ink-2">{cnn}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>
    </>
  );
}
