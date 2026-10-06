"""Loads the trained MSCAF-Net once and runs inference.

Uses the research code as-is: models.factory.build_model for the network and
preprocessing.transforms.get_eval_transforms for the input pipeline.
"""

import io
import threading
import time

import torch
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app import config
from models.factory import build_model
from preprocessing.transforms import get_eval_transforms


class InvalidImageError(ValueError):
    """Raised when an upload is not a usable image."""


def load_image(data: bytes) -> Image.Image:
    """Decodes uploaded bytes into an RGB PIL image, entirely in memory."""

    if not data:
        raise InvalidImageError("Uploaded file is empty.")

    Image.MAX_IMAGE_PIXELS = config.MAX_IMAGE_PIXELS

    try:
        # verify() checks integrity but leaves the image unusable, so reopen
        with Image.open(io.BytesIO(data)) as probe:
            image_format = probe.format
            probe.verify()

        image = Image.open(io.BytesIO(data))
        image.load()
    except Image.DecompressionBombError as exc:
        raise InvalidImageError("Image dimensions are too large.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InvalidImageError("File is not a valid or supported image.") from exc

    if image_format not in config.ALLOWED_IMAGE_FORMATS:
        raise InvalidImageError(f"Unsupported image format: {image_format}")

    # Phone photos store their rotation in EXIF; apply it so the model sees
    # the image the way the user does
    image = ImageOps.exif_transpose(image)

    return image.convert("RGB")


class ModelService:

    def __init__(self):
        self.device = torch.device(
            config.DEVICE or ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.model = None
        self.checkpoint_info = {}
        self.transform = get_eval_transforms(config.IMAGE_SIZE)

        # The model keeps per-forward state (AdaptiveFusion.last_weights) and
        # Grad-CAM keeps hook state, so every forward pass is serialized.
        self.lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def load(self):

        checkpoint = torch.load(
            config.CHECKPOINT_PATH,
            map_location=self.device,
            weights_only=False
        )

        model = build_model(
            config.MODEL_MODE,
            num_classes=config.NUM_CLASSES,
            pretrained=False,
            mscaf_kwargs=checkpoint["model_config"]["mscaf_kwargs"]
        )

        model.load_state_dict(
            checkpoint["model_state_dict"],
            strict=True
        )

        model.to(self.device)
        model.eval()

        self.checkpoint_info = {
            "epoch": checkpoint.get("epoch"),
            "mode": checkpoint["model_config"].get("mode"),
            "mscaf_kwargs": checkpoint["model_config"]["mscaf_kwargs"],
            "validation_accuracy": checkpoint.get("validation_accuracy"),
            "parameters": sum(p.numel() for p in model.parameters())
        }

        # Only the weights are needed from here on
        del checkpoint

        self.model = model

        # Warm-up so the first request doesn't pay for CUDA initialisation
        with self.lock, torch.inference_mode():
            self.model(torch.zeros(1, 3, config.IMAGE_SIZE, config.IMAGE_SIZE, device=self.device))

    def preprocess(self, image: Image.Image) -> torch.Tensor:
        return self.transform(image).unsqueeze(0).to(self.device)

    def predict(self, input_tensor: torch.Tensor) -> dict:
        """Class probabilities for a preprocessed (1, 3, H, W) tensor.

        Caller must hold `self.lock`.
        """

        start = time.perf_counter()

        with torch.inference_mode():
            logits = self.model(input_tensor)
            probabilities = logits.softmax(dim=1)[0].float().cpu()

        if self.device.type == "cuda":
            torch.cuda.synchronize()

        inference_ms = (time.perf_counter() - start) * 1000

        predicted_index = int(probabilities.argmax())

        return {
            "predicted_index": predicted_index,
            "predicted_class": config.CLASS_NAMES[predicted_index],
            "confidence": float(probabilities[predicted_index]),
            "class_probabilities": {
                name: float(probabilities[i])
                for i, name in enumerate(config.CLASS_NAMES)
            },
            "scale_fusion_weights": self._scale_fusion_weights(),
            "inference_ms": inference_ms
        }

    def _scale_fusion_weights(self):
        """Per-scale weight of the final adaptive fusion for the last image,
        averaged over channels (read-only view of AdaptiveFusion.last_weights)."""

        fusion = getattr(self.model, "scale_fusion", None)

        if fusion is None or fusion.last_weights is None:
            return None

        weights = fusion.last_weights[0].mean(dim=1).cpu()

        return {
            f"{s}x{s}": float(weights[i])
            for i, s in enumerate(self.model.scales)
        }
