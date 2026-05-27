import logging
from datetime import datetime, UTC

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.graph import create_workflow
from src.aml_workflow.llm import LLMClient
from src.aml_workflow.observability import setup as setup_observability, get_langgraph_callbacks, shutdown as shutdown_observability
from src.bff.config import DATA_DIR
from src.bff.logger import logger

DEFAULT_MODE = "full"


async def run_validation(upload_id: str, db: AsyncSession, llm: LLMClient | None = None, mode: str | None = None) -> None:
    from src.aml_workflow.models.upload_status import UploadStatus
    from src.file_processor.models import UploadedFiles

    effective_mode = mode or DEFAULT_MODE
    now = datetime.now(UTC).isoformat()

    logger.info("Workflow started for upload %s (mode=%s)", upload_id, effective_mode)

    upload = await db.get(UploadedFiles, upload_id)
    if upload:
        upload.status = "processing"
        upload.updated_at = now

    db.add(UploadStatus(
        upload_id=upload_id,
        status="processing",
        actor="system",
        created_at=now,
    ))
    await db.commit()

    try:
        setup_observability()

        async with AsyncSqliteSaver.from_conn_string(str(DATA_DIR / "checkpoints.db")) as checkpointer:
            app = create_workflow(db, llm, mode=effective_mode, checkpointer=checkpointer)
            callbacks = get_langgraph_callbacks()
            config: dict = {"configurable": {"thread_id": upload_id}}
            if callbacks:
                config["callbacks"] = callbacks
            result = await app.ainvoke({"upload_id": upload_id}, config)

            if "__interrupt__" in result:
                logger.info("Workflow paused for upload %s — awaiting human review", upload_id)
                return

        shutdown_observability()
        logger.info("Workflow completed for upload %s", upload_id)
        if upload:
            upload.status = "complete"
            upload.updated_at = datetime.now(UTC).isoformat()
        db.add(UploadStatus(
            upload_id=upload_id,
            status="complete",
            actor="system",
            created_at=datetime.now(UTC).isoformat(),
        ))
        await db.commit()
    except Exception as e:
        shutdown_observability()
        logger.error("Workflow failed for upload %s: %s: %s", upload_id, type(e).__name__, e, exc_info=True)
        if upload:
            upload.status = "failed"
            upload.updated_at = datetime.now(UTC).isoformat()
        db.add(UploadStatus(
            upload_id=upload_id,
            status="failed",
            actor="system",
            created_at=datetime.now(UTC).isoformat(),
        ))
        await db.commit()
        raise
