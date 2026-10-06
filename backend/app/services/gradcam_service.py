"""Grad-CAM for the web API, built on the research implementation.

explainability.gradcam.GradCAM does the computation; the heatmap colouring
and overlay reuse the helpers from explainability.run_gradcam so the images
match the research figures.
"""

import base64
import io
import time

import cv2
import numpy as np
import torch
from PIL import Image

from explainability.gradcam import GradCAM
from explainability.run_gradcam import denormalize, overlay_heatmap

TARGET_LAYER_NAME = "fusion_identity"


def _png_base64(image_rgb: np.ndarray) -> str:
    buffer = io.BytesIO()
    Image.fromarray(image_rgb).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class GradCAMService:

    def __init__(self, model: torch.nn.Module):
        self.model = model
        # Hooks are registered once here; never create GradCAM per request
        self.gradcam = GradCAM(model, getattr(model, TARGET_LAYER_NAME))

    def generate(self, input_tensor: torch.Tensor, class_idx: int) -> dict:
        """Heatmap + overlay for `class_idx`.

        Caller must hold the model lock. Gradients are explicitly enabled,
        because the backward pass fails under no_grad / inference_mode.
        """

        start = time.perf_counter()

        try:
            with torch.enable_grad():
                cam = self.gradcam.generate(input_tensor, class_idx=class_idx)
        finally:
            # Free parameter gradients and hook tensors between requests
            self.model.zero_grad(set_to_none=True)
            self.gradcam.activations = None
            self.gradcam.gradients = None

        image_rgb = denormalize(input_tensor[0])
        overlay = overlay_heatmap(image_rgb, cam)

        heatmap = cv2.applyColorMap((cam * 255).astype(np.uint8), cv2.COLORMAP_JET)
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

        return {
            "heatmap_png_base64": _png_base64(heatmap),
            "overlay_png_base64": _png_base64(overlay),
            "gradcam_ms": (time.perf_counter() - start) * 1000
        }
