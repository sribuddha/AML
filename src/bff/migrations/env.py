from pathlib import Path

from alembic import context
from sqlalchemy import create_engine

from src.bff.database import Base

# ── Ensure all model classes are registered in Base.metadata ──
import src.core.models.account           # noqa: F401, E402
import src.core.models.customer          # noqa: F401, E402
import src.core.models.enrichment_snapshot  # noqa: F401, E402
import src.core.models.rule              # noqa: F401, E402
import src.core.models.sar               # noqa: F401, E402
import src.core.models.transaction       # noqa: F401, E402
import src.core.models.uploaded_files    # noqa: F401, E402
import src.core.models.validation_result # noqa: F401, E402
import src.aml_workflow.models.upload_status    # noqa: F401, E402
import src.aml_workflow.models.transaction_status  # noqa: F401, E402
import src.file_processor.models as _fp_models    # noqa: F401, E402

config = context.config

from src.bff.config import get_database_url  # noqa: E402
_db_url = get_database_url()
config.set_main_option("sqlalchemy.url", _db_url.replace("+aiosqlite", ""))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_db_url.replace("+aiosqlite", ""))
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
