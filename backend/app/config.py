"""Backend configuration.

All paths are derived from the location of this file, so the backend works
regardless of the drive letter / folder the project lives in.
"""

import os
import sys
from pathlib import Path

# backend/app/config.py -> parents[2] is the project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# The research packages (models/, preprocessing/, explainability/) live at
# the project root and are imported as top-level packages.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CHECKPOINT_PATH = Path(
    os.environ.get(
        "MSCAF_CHECKPOINT",
        PROJECT_ROOT / "checkpoints" / "baseline_mscaf_full_best.pth"
    )
)

RESULTS_DIR = PROJECT_ROOT / "results"

MODEL_MODE = "mscaf"
NUM_CLASSES = 3
IMAGE_SIZE = 224

# Same order as the ImageFolder class indices used in training/evaluation
CLASS_NAMES = [
    "angular_leaf_spot",
    "bean_rust",
    "healthy"
]

# "cuda" / "cpu"; defaults to CUDA when available
DEVICE = os.environ.get("MSCAF_DEVICE")

# Upload limits
MAX_UPLOAD_BYTES = int(os.environ.get("MSCAF_MAX_UPLOAD_MB", "10")) * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF", "MPO"}

# Origins allowed to call the API from a browser (future frontend dev servers)
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "MSCAF_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]

# Research results of the full model on the 128-image test set
# (results/test_metrics_mscaf_full.json). Reported as-is, not recomputed.
RESEARCH_METRICS = {
    "accuracy": 99.22,
    "precision": 99.24,
    "recall": 99.22,
    "f1_score": 99.22,
    "correct": 127,
    "total": 128,
    "averaging": "weighted",
    "source": "results/test_metrics_mscaf_full.json"
}
