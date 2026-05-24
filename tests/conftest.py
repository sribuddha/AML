import asyncio
import os
import shutil
import tempfile
from datetime import datetime, UTC
from pathlib import Path

import pytest
import pytest_asyncio
from faker import Faker
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import src.bff.database as db_mod
from src.bff.app import lifespan
from src.bff.models.customer import Customer
from src.bff.models.account import Account
from src.bff.config import UPLOAD_DIR
from src.bff.database import Base, get_db
from src.file_processor.models import RejectedRecord, Transaction, UploadedFiles
from src.aml_workflow.models.enrichment_snapshot import EnrichmentSnapshot

fake = Faker()

_test_uploads: set[str] = set()
_upload_files_snapshot: set[str] = set()


def _track_upload_id(mapper, connection, target):
    _test_uploads.add(target.id)


event.listen(UploadedFiles, "after_insert", _track_upload_id)


@pytest_asyncio.fixture(scope="session")
async def engine():
    db_file = Path(tempfile.mktemp(suffix=".db"))
    url = f"sqlite+aiosqlite:///{db_file}"

    # point the global engine + factory at this test's DB so background tasks
    # (which use async_session_factory) connect here too
    os.environ["AML_DATABASE_URL"] = url
    old_engine = db_mod.engine
    db_mod.engine = create_async_engine(url, echo=False)
    db_mod.async_session_factory = async_sessionmaker(
        db_mod.engine, class_=AsyncSession, expire_on_commit=False
    )
    await old_engine.dispose()

    engine = create_async_engine(url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()
    await db_mod.engine.dispose()
    for _ in range(10):
        try:
            db_file.unlink()
            break
        except PermissionError:
            await asyncio.sleep(0.05)


@pytest_asyncio.fixture
async def session(engine):
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        yield s
        for table in reversed(Base.metadata.sorted_tables):
            await s.execute(table.delete())
        await s.commit()


@pytest_asyncio.fixture
async def seeded_session(engine):
    async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
        now = datetime.now(UTC).isoformat()
        customers = [
            Customer(customer_id="CUST001", first_name="John", last_name="Doe",
                     address_line="123 Main St", city="NYC", state="NY", zip="10001",
                     created_at=now, updated_at=now),
            Customer(customer_id="CUST002", first_name="Jane", last_name="Smith",
                     address_line="456 Oak Ave", city="LA", state="CA", zip="90001",
                     created_at=now, updated_at=now),
            Customer(customer_id="CUST003", first_name="Bob", last_name="Jones",
                     address_line="789 Pine Rd", city="Chicago", state="IL", zip="60601",
                     created_at=now, updated_at=now),
        ]
        s.add_all(customers)

        accounts = [
            Account(account_id="ACC001", customer_id="CUST001", name="Checking",
                    bank="Bank of America", date_opened="2020-01-15", type="checking",
                    created_at=now, updated_at=now),
            Account(account_id="ACC002", customer_id="CUST001", name="Savings",
                    bank="Bank of America", date_opened="2021-03-10", type="savings",
                    created_at=now, updated_at=now),
            Account(account_id="ACC003", customer_id="CUST002", name="Checking",
                    bank="Chase", date_opened="2022-06-01", type="checking",
                    created_at=now, updated_at=now),
            Account(account_id="ACC004", customer_id="CUST003", name="Credit",
                    bank="Citi", date_opened="2023-01-01", type="credit",
                    created_at=now, updated_at=now),
        ]
        s.add_all(accounts)
        await s.commit()
        yield s
        for table in reversed(Base.metadata.sorted_tables):
            await s.execute(table.delete())
        await s.commit()


@pytest_asyncio.fixture(autouse=True)
async def _cleanup_staging(engine):
    global _test_uploads, _upload_files_snapshot
    _test_uploads.clear()
    _upload_files_snapshot = {p.name for p in UPLOAD_DIR.iterdir() if p.is_file()}
    yield
    for uid in list(_test_uploads):
        staging_dir = UPLOAD_DIR / "staging" / str(uid)
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
    for p in UPLOAD_DIR.iterdir():
        if p.is_file() and p.name not in _upload_files_snapshot:
            p.unlink()


@pytest_asyncio.fixture
async def app(engine):
    app = FastAPI(title="AML BFF Test")

    from src.file_processor.rest.upload import router
    app.include_router(router)
    from src.file_processor.rest.read import router as read_router
    app.include_router(read_router)
    from src.file_processor.rest.reprocess import router as reprocess_router
    app.include_router(reprocess_router)
    from src.aml_workflow.rest.rules import router as rules_router
    app.include_router(rules_router)
    from src.aml_workflow.rest.sar import router as sar_router
    app.include_router(sar_router)
    from src.aml_workflow.rest.audit import router as audit_router
    app.include_router(audit_router)
    from src.aml_workflow.rest.validation import router as validation_router
    app.include_router(validation_router)

    async def override_get_db():
        async with async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)() as s:
            yield s
    yield app
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_csv_path(tmp_path: Path) -> Path:
    """Create a sample CSV file for E2E testing."""
    content = (
        "account_id,customer_id,amount,counterparty,location,date,source_txn_id\n"
        "ACC001,CUST001,1500.00,Acme Corp,New York,2026-05-01,TXN001\n"
        "ACC003,CUST002,25000.00,Global Trading,London,2026-05-02,TXN002\n"
        "ACC001,CUST001,-500.00,Refund Co,Chicago,2026-05-03,TXN003\n"
        "ACC004,CUST003,75.50,Local Shop,Boston,2026-05-04,TXN004\n"
        "ACC002,CUST001,100000.00,Offshore Ltd,Cayman,2026-05-05,TXN005\n"
        "ACC003,CUST002,0.00,Zero Inc,Dallas,2026-05-06,TXN006\n"
        "ACC999,CUST001,500.00,Fake Corp,Miami,2026-05-07,TXN007\n"
        "ACC001,CUST999,300.00,Bad Row,Seattle,2026-05-08,TXN008\n"
        "ACC001,CUST001,abc,TestCorp,New York,2026-05-10,TXN009\n"
        "ACC001,CUST001,100.00,,,2026-05-11,TXN010\n"
    )
    path = tmp_path / "test_transactions.csv"
    path.write_text(content)
    return path


@pytest.fixture
def empty_csv_path(tmp_path: Path) -> Path:
    content = "account_id,customer_id,amount,counterparty,location,date,source_txn_id\n"
    path = tmp_path / "empty.csv"
    path.write_text(content)
    return path
