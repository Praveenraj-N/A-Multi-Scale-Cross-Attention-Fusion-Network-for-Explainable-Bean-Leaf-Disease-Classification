import torch
from fastapi import APIRouter, HTTPException, Request

from backend.app import config
from backend.app.schemas import HealthResponse, ModelInfoResponse, ResearchMetrics
from backend.app.services.gradcam_service import TARGET_LAYER_NAME

router = APIRouter(tags=["info"])


@router.get("/health", response_model=HealthResponse)
def health(request: Request):

    model_service = request.app.state.model_service
    cuda = torch.cuda.is_available()

    return HealthResponse(
        status="ok" if model_service.loaded else "loading",
        model_loaded=model_service.loaded,
        device=str(model_service.device),
        cuda_available=cuda,
        gpu_name=torch.cuda.get_device_name(0) if cuda else None
    )


@router.get("/model-info", response_model=ModelInfoResponse)
def model_info(request: Request):

    model_service = request.app.state.model_service

    if not model_service.loaded:
        raise HTTPException(status_code=503, detail="Model is not loaded.")

    info = model_service.checkpoint_info
    kwargs = info["mscaf_kwargs"]

    return ModelInfoResponse(
        name="MSCAF-Net (Multi-Scale Cross-Attention Fusion Network)",
        mode=info["mode"],
        checkpoint=config.CHECKPOINT_PATH.relative_to(config.PROJECT_ROOT).as_posix(),
        checkpoint_epoch=info["epoch"],
        checkpoint_validation_accuracy=info["validation_accuracy"],
        parameters_millions=round(info["parameters"] / 1e6, 2),
        backbones=["PVT v2-B2 (transformer branch)", "GCADSN (CNN branch)"],
        scales=list(kwargs["scales"]),
        feature_dim=kwargs["dim"],
        attention_heads=kwargs["num_heads"],
        cross_attention=kwargs["use_cross_attention"],
        fusion=kwargs["fusion"],
        dropout=kwargs["dropout"],
        classes=config.CLASS_NAMES,
        input_size=[config.IMAGE_SIZE, config.IMAGE_SIZE],
        preprocessing=[
            f"Resize to {config.IMAGE_SIZE}x{config.IMAGE_SIZE}",
            "ToTensor (scale to [0, 1])",
            "Normalize (ImageNet mean [0.485, 0.456, 0.406], std [0.229, 0.224, 0.225])"
        ],
        gradcam_target_layer=f"{TARGET_LAYER_NAME} (fused map of the 7x7 scale)",
        device=str(model_service.device),
        research_metrics=ResearchMetrics(**config.RESEARCH_METRICS)
    )
