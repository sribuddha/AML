from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.file_processor.rest.upload import router as file_processor_router
from src.file_processor.rest.read import router as read_router
from src.file_processor.rest.reprocess import router as reprocess_router
from src.aml_workflow.rest.rules import router as rules_router
from src.aml_workflow.rest.sar import router as sar_router
from src.aml_workflow.rest.audit import router as audit_router
from src.aml_workflow.rest.validation import router as validation_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    alembic_cfg = Config(Path(__file__).parent / "alembic.ini")
    command.upgrade(alembic_cfg, "head")
    yield


app = FastAPI(title="AML BFF", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(file_processor_router)
app.include_router(read_router)
app.include_router(reprocess_router)
app.include_router(rules_router)
app.include_router(sar_router)
app.include_router(audit_router)
app.include_router(validation_router)
