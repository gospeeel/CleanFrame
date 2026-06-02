from pathlib import Path
from uuid import uuid4
import logging

from fastapi import File, HTTPException, UploadFile, status

from llm.core.metrics import record_error
from llm.core.structured_logging import log_event
from llm.core.model_runtime import model_status
from llm.paths import DEFAULT_MODEL_DIR, UPLOADS_DIR

SUPPORTED_EXTENSIONS = {".docx", ".pdf", ".txt"}
logger = logging.getLogger(__name__)


async def run_analysis(
    file: UploadFile = File(...),
    target_rating: str | None = None,
    analysis_id: str | None = None,
    request_id: str | None = None,
):
    log_event(
        logger,
        "analysis.request.received",
        analysis_id=analysis_id,
        request_id=request_id,
        filename=file.filename,
        target_rating=target_rating,
    )
    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()

    if not original_name or extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поддерживаются только файлы .docx, .pdf и .txt",
        )

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOADS_DIR / f"{uuid4().hex}_{original_name}"

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Загруженный файл пуст",
        )

    with open(save_path, "wb") as f:
        f.write(content)

    try:
        readiness = model_status()
        if not readiness["ready"]:
            record_error("rubert")
            raise FileNotFoundError(
                f"RuBERT модель недоступна: {readiness.get('error')}. "
                "Проверьте llm/trained_model и mount /models/trained_model."
            )

        from llm.pipeline.full_pipeline import process_script

        result = process_script(
            input_path=save_path,
            analysis_id=analysis_id,
            request_id=request_id,
            target_rating=target_rating,
        )
    except FileNotFoundError as exc:
        record_error("file_or_model")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        record_error("validation")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        record_error("pipeline")
        logger.exception("Script processing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обработки сценария: {exc}",
        ) from exc
    finally:
        save_path.unlink(missing_ok=True)

    return {
        "detail": "Все успешно загрузилось",
        "result": result,
    }
