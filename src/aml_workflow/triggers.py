import logging

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import update as sa_update

from src.aml_workflow.graph import create_workflow
from src.aml_workflow.llm import LLMClient
from src.core.models.uploaded_files import UploadedFiles
from src.core.observability import setup as setup_observability, get_langgraph_callbacks, shutdown as shutdown_observability
from src.aml_workflow.services import transition_upload
from src.bff.config import get_data_dir
from src.bff.logger import logger

DEFAULT_MODE = "full"


async def _persist_mode(upload_id: str, mode: str, db: AsyncSession) -> None:
    await db.execute(
        sa_update(UploadedFiles).where(UploadedFiles.id == upload_id).values(mode=mode)
    )
    await db.commit()


async def run_validation(upload_id: str, db: AsyncSession, llm: LLMClient | None = None, mode: str | None = None) -> None:
    effective_mode = mode or DEFAULT_MODE

    logger.info("Workflow started for upload %s (mode=%s)", upload_id, effective_mode)

    await _persist_mode(upload_id, effective_mode, db)
    await transition_upload(db, upload_id, "processing")

    try:
        setup_observability()

        async with AsyncSqliteSaver.from_conn_string(str(get_data_dir() / "checkpoints.db")) as checkpointer:
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
        await transition_upload(db, upload_id, "complete")
    except Exception as e:
        shutdown_observability()
        logger.error("Workflow failed for upload %s: %s: %s", upload_id, type(e).__name__, e, exc_info=True)
        await transition_upload(db, upload_id, "failed")
        raise
