// MOCK DATA - for UI development only (VITE_USE_MOCK=true).
// Shape mirrors the FastAPI POST /predict response. Values were captured from
// one real backend run on the sample leaf in /public/mock, but in mock mode
// they are replayed for ANY uploaded image, so they must never be presented
// as a prediction. The UI shows a "Mock data" banner whenever isMock is true.

export const MOCK_IMAGES = {
  original: "/mock/mock-original.jpg",
  heatmap: "/mock/mock-heatmap.png",
  overlay: "/mock/mock-overlay.png"
};

export const MOCK_PREDICTION = {
  isMock: true,
  predicted_class: "angular_leaf_spot",
  predicted_index: 0,
  confidence: 0.9999993,
  class_probabilities: {
    angular_leaf_spot: 0.9999993,
    bean_rust: 7.75e-7,
    healthy: 1.89e-8
  },
  scale_fusion_weights: {
    "28x28": 0.2134,
    "14x14": 0.3164,
    "7x7": 0.4702
  },
  gradcam: {
    status: "success",
    target_class: "angular_leaf_spot",
    target_layer: "fusion_identity",
    heatmap_url: MOCK_IMAGES.heatmap,
    overlay_url: MOCK_IMAGES.overlay,
    error: null
  },
  processing: {
    device: "mock",
    filename: "mock-original.jpg",
    original_size: [730, 730],
    input_size: [224, 224],
    inference_ms: 38.45,
    gradcam_ms: 127.21,
    total_ms: 176.17
  }
};
