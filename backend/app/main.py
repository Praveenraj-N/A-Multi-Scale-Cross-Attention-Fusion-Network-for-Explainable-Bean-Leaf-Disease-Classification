"""FastAPI backend for MSCAF-Net bean leaf disease classification.

Run from the project root with a single worker (one model copy in memory):

    .venv\\Scripts\\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app import config  # sets up sys.path for the research packages
from backend.app.routers import info, predict
from backend.app.services.gradcam_service import GradCAMService
from backend.app.services.model_service import ModelService

logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")
logger = logging.getLogger("mscaf")


@asynccontextmanager
async def lifespan(app: FastAPI):

    model_service = ModelService()
    app.state.model_service = model_service

    logger.info("Loading %s on %s", config.CHECKPOINT_PATH, model_service.device)
    model_service.load()
    logger.info(
        "Model loaded (epoch %s, %s)",
        model_service.checkpoint_info["epoch"],
        model_service.checkpoint_info["mscaf_kwargs"]
    )

    app.state.gradcam_service = GradCAMService(model_service.model)
    logger.info("Grad-CAM ready")

    yield


app = FastAPI(
    title="MSCAF-Net API",
    description="Bean leaf disease classification with Grad-CAM explanations.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)

app.include_router(info.router)
app.include_router(predict.router)
