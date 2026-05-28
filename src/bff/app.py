from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.file_processor.rest.upload import router as file_processor_router
from src.file_processor.rest.read import router as read_router
from src.file_processor.rest.reprocess import router as reprocess_router
from src.aml_workflow.rest.rules import router as rules_router
from src.aml_workflow.rest.sar import router as sar_router
from src.aml_workflow.rest.audit import router as audit_router
from src.aml_workflow.rest.validation import router as validation_router
from src.bff.routes.transactions import router as transactions_router
from src.bff.routes.customers import router as customers_router
from src.bff.routes.accounts import router as accounts_router
from src.bff.routes.compliance import router as compliance_router
from src.bff.routes.generate import router as generate_router
from src.bff.routes.operations import router as operations_router
from src.bff.routes.eval import router as eval_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    alembic_cfg = Config(Path(__file__).parent / "alembic.ini")
    command.upgrade(alembic_cfg, "head")
    yield


app = FastAPI(title="AML BFF", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(file_processor_router)
# Order matters: /search (static path) must be registered before /{upload_id} (dynamic param)
app.include_router(operations_router)
app.include_router(read_router)
app.include_router(reprocess_router)
app.include_router(rules_router)
app.include_router(compliance_router)
app.include_router(sar_router)
app.include_router(eval_router)
app.include_router(audit_router)
app.include_router(validation_router)
app.include_router(transactions_router)
app.include_router(customers_router)
app.include_router(accounts_router)
app.include_router(generate_router)

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

frontend_dist = Path(__file__).parent.parent.parent /     "ui" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        file = frontend_dist / full_path if full_path else frontend_dist
        if file.is_file():
            return FileResponse(str(file))
        index = frontend_dist / "index.html"
        if index.exists():
            return FileResponse(str(index))
        raise HTTPException(status_code=404)
