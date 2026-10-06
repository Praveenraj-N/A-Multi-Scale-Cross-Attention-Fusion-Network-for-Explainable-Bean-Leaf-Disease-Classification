from typing import Dict, List, Optional

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    device: str
    cuda_available: bool
    gpu_name: Optional[str] = None


class ResearchMetrics(BaseModel):
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    correct: int
    total: int
    averaging: str
    source: str


class ModelInfoResponse(BaseModel):
    name: str
    mode: str
    checkpoint: str
    checkpoint_epoch: int
    checkpoint_validation_accuracy: Optional[float] = None
    parameters_millions: float
    backbones: List[str]
    scales: List[int]
    feature_dim: int
    attention_heads: int
    cross_attention: bool
    fusion: str
    dropout: float
    classes: List[str]
    input_size: List[int]
    preprocessing: List[str]
    gradcam_target_layer: str
    device: str
    research_metrics: ResearchMetrics


class GradCAMResult(BaseModel):
    status: str  # "success" | "failed"
    target_class: Optional[str] = None
    target_layer: Optional[str] = None
    heatmap_png_base64: Optional[str] = None
    overlay_png_base64: Optional[str] = None
    error: Optional[str] = None


class ProcessingInfo(BaseModel):
    device: str
    filename: Optional[str] = None
    original_size: List[int]
    input_size: List[int]
    inference_ms: float
    gradcam_ms: Optional[float] = None
    total_ms: float


class PredictResponse(BaseModel):
    predicted_class: str
    predicted_index: int
    confidence: float
    class_probabilities: Dict[str, float]
    scale_fusion_weights: Optional[Dict[str, float]] = None
    gradcam: Optional[GradCAMResult] = None
    processing: ProcessingInfo
