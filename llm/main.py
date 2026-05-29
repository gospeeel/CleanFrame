import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status

from llm.core.model_runtime import model_status, warm_model
from llm.observability import configure_sentry
from llm.router import router as llm_router


logger = logging.getLogger(__name__)
configure_sentry()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("LLM_PRELOAD_MODEL", "true").lower() in {"1", "true", "yes"}:
        try:
            warm_model()
            logger.info("RuBERT model preloaded")
        except Exception as exc:
            logger.warning("RuBERT model was not preloaded: %s", exc)
    yield


app = FastAPI(title="ML_WINK LLM Service", lifespan=lifespan)

app.include_router(llm_router)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok"}


@app.get("/ready", tags=["health"])
async def ready_check(response: Response):
    status_payload = model_status(warm=True)
    if not status_payload["ready"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return status_payload
