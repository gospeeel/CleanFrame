from fastapi import APIRouter, File, Form, Header, UploadFile

from llm.core.metrics import metrics_snapshot
from llm.llm_client import ollama_status
from llm.core.model_runtime import model_status
from llm.schemas import Allm
from llm.service import run_analysis

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.post("/run", response_model=Allm)
async def run_analysis_api(
    file: UploadFile = File(...),
    target_rating: str | None = Form(default=None),
    x_analysis_id: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
):
    return await run_analysis(
        file,
        target_rating=target_rating,
        analysis_id=x_analysis_id,
        request_id=x_request_id,
    )


@router.get("/health")
async def analysis_health():
    return {
        "status": "ok",
        "rubert": model_status(warm=False),
        "ollama": ollama_status(),
    }


@router.get("/metrics")
async def analysis_metrics():
    return metrics_snapshot()
