// Verified research results. Sources:
//   results/test_metrics_mscaf_{A,B,C,full}.json
//   results/classification_report_mscaf_{A,B,C,full}.txt
//   FINAL_PROJECT_INFO.txt (base fusion result, misclassified sample)
//   checkpoints/baseline_mscaf_full_best.pth (model_config, epoch)
// These are test-set results, not per-image prediction confidence.

export const TEST_SET = {
  name: "iBean test subset",
  size: 128,
  statement: "Evaluation performed on the frozen 128-image iBean test subset."
};

export const FULL_MODEL_METRICS = {
  accuracy: 99.22,
  precision: 99.24,
  recall: 99.22,
  f1: 99.22,
  correct: 127,
  incorrect: 1,
  total: 128,
  averaging: "weighted"
};

export const MODEL_CONFIG = {
  name: "MSCAF-Net",
  fullName: "Multi-Scale Cross-Attention Fusion Network",
  scales: [28, 14, 7],
  dim: 128,
  heads: 4,
  crossAttention: true,
  fusion: "Adaptive",
  dropout: 0.1,
  checkpointEpoch: 21,
  parametersM: 26.13,
  inputSize: 224,
  checkpoint: "checkpoints/baseline_mscaf_full_best.pth",
  gradcamLayer: "fusion_identity"
};

// Per-class report of the full model (classification_report_mscaf_full.txt)
export const CLASS_REPORT = [
  { id: "angular_leaf_spot", precision: 1.0, recall: 1.0, f1: 1.0, support: 43 },
  { id: "bean_rust", precision: 0.9773, recall: 1.0, f1: 0.9885, support: 43 },
  { id: "healthy", precision: 1.0, recall: 0.9762, f1: 0.988, support: 42 }
];

// Rows = true class, columns = predicted class (same order as CLASSES)
export const CONFUSION_MATRIX = [
  [43, 0, 0],
  [0, 43, 0],
  [0, 1, 41]
];

export const ABLATION = [
  {
    id: "base",
    name: "Base Fusion",
    description: "PVT + GCADSN, last feature maps concatenated (base paper network)",
    accuracy: 97.66,
    precision: null,
    recall: null,
    f1: null,
    config: null
  },
  {
    id: "A",
    name: "MSCAF-A",
    description: "7×7 scale only, concatenation, no cross-attention",
    accuracy: 96.88,
    precision: 96.91,
    recall: 96.88,
    f1: 96.88,
    epoch: 17,
    config: { scales: [7], crossAttention: false, fusion: "Concat" },
    confusion: [[42, 1, 0], [2, 41, 0], [0, 1, 41]]
  },
  {
    id: "B",
    name: "MSCAF-B",
    description: "Adds multi-scale fusion (28, 14, 7), concatenation",
    accuracy: 97.66,
    precision: 97.71,
    recall: 97.66,
    f1: 97.66,
    epoch: 11,
    config: { scales: [28, 14, 7], crossAttention: false, fusion: "Concat" },
    confusion: [[43, 0, 0], [2, 41, 0], [0, 1, 41]]
  },
  {
    id: "C",
    name: "MSCAF-C",
    description: "Adds bidirectional cross-attention, concatenation",
    accuracy: 96.88,
    precision: 96.99,
    recall: 96.88,
    f1: 96.87,
    epoch: 29,
    config: { scales: [28, 14, 7], crossAttention: true, fusion: "Concat" },
    confusion: [[43, 0, 0], [3, 40, 0], [0, 1, 41]]
  },
  {
    id: "full",
    name: "MSCAF-Full",
    description: "Adds adaptive fusion (the full MSCAF-Net)",
    accuracy: 99.22,
    precision: 99.24,
    recall: 99.22,
    f1: 99.22,
    epoch: 21,
    config: { scales: [28, 14, 7], crossAttention: true, fusion: "Adaptive" },
    confusion: CONFUSION_MATRIX
  }
];

export const FAILURE_CASE = {
  file: "healthy_test.35.jpg",
  trueClass: "healthy",
  predictedClass: "bean_rust",
  confidence: 96.35,
  figure: "/research/gradcam_misclassified_healthy35.png"
};

// Public iBean split. Augmented counts follow preprocessing/augment_dataset.py:
// the original plus 8 fixed augmentations = 9 images per source image
// (train and validation only; the test set is never augmented).
export const DATASET = {
  name: "iBean",
  origin: "Smartphone photos of bean leaves taken in fields in Uganda (Makerere AI Lab).",
  augmentationFactor: 9,
  augmentations: [
    "Rotation 30° clockwise",
    "Rotation 30° counter-clockwise",
    "Rotation 60° clockwise",
    "Rotation 60° counter-clockwise",
    "Horizontal flip",
    "Vertical flip",
    "Horizontal translation (15%)",
    "Vertical translation (15%)"
  ],
  splits: [
    { id: "train", label: "Train", counts: { angular_leaf_spot: 345, bean_rust: 348, healthy: 341 }, augmented: true },
    { id: "validation", label: "Validation", counts: { angular_leaf_spot: 44, bean_rust: 45, healthy: 44 }, augmented: true },
    { id: "test", label: "Test", counts: { angular_leaf_spot: 43, bean_rust: 43, healthy: 42 }, augmented: false }
  ]
};

export const RESEARCH_FIGURES = [
  { src: "/research/gradcam_3class_mscaf_full.png", title: "Grad-CAM for one test image per class", source: "results/gradcam_3class_mscaf_full.png" },
  { src: "/research/confusion_matrix_mscaf_full.png", title: "Confusion matrix, full model", source: "results/confusion_matrix_mscaf_full.png" },
  { src: "/research/ablation_comparison_mscaf.png", title: "Ablation comparison", source: "results/ablation_comparison_mscaf.png" },
  { src: "/research/training_curves_mscaf_full.png", title: "Training curves, full model", source: "results/training_curves_mscaf_full.png" }
];
