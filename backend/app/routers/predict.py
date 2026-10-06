import logging
import time

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from backend.app import config
from backend.app.schemas import GradCAMResult, PredictResponse, ProcessingInfo
from backend.app.services.gradcam_service import TARGET_LAYER_NAME
from backend.app.services.model_service import InvalidImageError, load_image

logger = logging.getLogger(__name__)

router = APIRouter(tags=["prediction"])


# Plain `def`: FastAPI runs it in a worker thread, so the blocking model call
# doesn't stall the event loop. The model lock serializes the GPU work.
@router.post("/predict", response_model=PredictResponse)
def predict(
    request: Request,
    file: UploadFile = File(..., description="Bean leaf image (JPEG/PNG/WEBP/BMP/TIFF)"),
    gradcam: bool = Query(True, description="Also compute the Grad-CAM heatmap and overlay")
):
    total_start = time.perf_counter()

    model_service = request.app.state.model_service
    gradcam_service = request.app.state.gradcam_service

    if not model_service.loaded:
        raise HTTPException(status_code=503, detail="Model is not loaded.")

    data = file.file.read(config.MAX_UPLOAD_BYTES + 1)

    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB)."
        )

    try:
        image = load_image(data)
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    input_tensor = model_service.preprocess(image)

    gradcam_result = None
    gradcam_ms = None

    with model_service.lock:

        result = model_service.predict(input_tensor)

        if gradcam:
            try:
                cam = gradcam_service.generate(input_tensor, class_idx=result["predicted_index"])
                gradcam_ms = cam.pop("gradcam_ms")
                gradcam_result = GradCAMResult(
                    status="success",
                    target_class=result["predicted_class"],
                    target_layer=TARGET_LAYER_NAME,
                    **cam
                )
            except Exception as exc:  # prediction is still useful without Grad-CAM
                logger.exception("Grad-CAM failed")
                gradcam_result = GradCAMResult(status="failed", error=str(exc))

    return PredictResponse(
        predicted_class=result["predicted_class"],
        predicted_index=result["predicted_index"],
        confidence=result["confidence"],
        class_probabilities=result["class_probabilities"],
        scale_fusion_weights=result["scale_fusion_weights"],
        gradcam=gradcam_result,
        processing=ProcessingInfo(
            device=str(model_service.device),
            filename=file.filename,
            original_size=list(image.size),
            input_size=[config.IMAGE_SIZE, config.IMAGE_SIZE],
            inference_ms=round(result["inference_ms"], 2),
            gradcam_ms=round(gradcam_ms, 2) if gradcam_ms is not None else None,
            total_ms=round((time.perf_counter() - total_start) * 1000, 2)
        )
    )
