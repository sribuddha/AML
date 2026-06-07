"""Verify ORM model schema matches migration-built schema.

Uses Alembic to build a fresh DB from all migrations, then compares
every column in Base.metadata against the reflected schema. Any
column/table mismatch fails — preventing the kind of drift that caused
the Docker-only "no such column: status" error.
"""

import os
import tempfile
from pathlib import Path

from alembic.command import upgrade as alembic_upgrade
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect

# Types considered equivalent on SQLite (no native JSON, etc.)
_EQUIVALENT_TYPES = {
    ("json", "varchar"),
    ("json", "text"),
}


def test_no_schema_drift():
    db_file = Path(tempfile.mktemp(suffix=".db"))
    sync_url = f"sqlite:///{db_file}"
    os.environ["AML_DATABASE_URL"] = sync_url.replace("sqlite://", "sqlite+aiosqlite://")

    _alembic_cfg = AlembicConfig(str(Path("src/bff/alembic.ini").resolve()))
    _alembic_cfg.set_main_option(
        "script_location", str(Path("src/bff/migrations").resolve()),
    )
    alembic_upgrade(_alembic_cfg, "head")

    engine = create_engine(sync_url)
    inspector = inspect(engine)
    db_tables = set(inspector.get_table_names())

    # Ensure all models are registered in Base.metadata
    from src.bff.database import Base
    import src.core.models.account          # noqa: F401
    import src.core.models.customer         # noqa: F401
    import src.core.models.enrichment_snapshot  # noqa: F401
    import src.core.models.rule             # noqa: F401
    import src.core.models.sar              # noqa: F401
    import src.core.models.transaction      # noqa: F401
    import src.core.models.uploaded_files   # noqa: F401
    import src.core.models.validation_result  # noqa: F401
    import src.aml_workflow.models.upload_status  # noqa: F401
    import src.aml_workflow.models.transaction_status  # noqa: F401
    import src.aml_workflow.models.workflow_job  # noqa: F401
    import src.file_processor.models        # noqa: F401

    orm_tables = {t.name: t for t in Base.metadata.sorted_tables}

    errors: list[str] = []

    # Every ORM table must exist in the migration-built DB
    for table_name, table in orm_tables.items():
        if table_name not in db_tables:
            errors.append(f"Table '{table_name}' exists in ORM but not in migration schema")
            continue

        db_columns = {c["name"]: c for c in inspector.get_columns(table_name)}
        for orm_col in table.columns:
            col_name = orm_col.name
            if col_name not in db_columns:
                errors.append(f"Column '{table_name}.{col_name}' exists in ORM but not in migration schema")
                continue

            db_col = db_columns[col_name]
            orm_type = str(orm_col.type).split("(")[0].lower()
            db_type = str(db_col["type"]).split("(")[0].lower()
            if orm_type != db_type and (orm_type, db_type) not in _EQUIVALENT_TYPES:
                errors.append(
                    f"Type mismatch '{table_name}.{col_name}': "
                    f"ORM={orm_col.type}, DB={db_col['type']}"
                )
            if orm_col.nullable != db_col.get("nullable"):
                errors.append(
                    f"Nullable mismatch '{table_name}.{col_name}': "
                    f"ORM={orm_col.nullable}, DB={db_col.get('nullable')}"
                )

    # Every DB table (except Alembic's) must have an ORM model
    known_extra = {"alembic_version"}
    for table_name in db_tables:
        if table_name not in orm_tables and table_name not in known_extra:
            errors.append(
                f"Table '{table_name}' exists in migration schema but has no ORM model"
            )

    engine.dispose()
    try:
        db_file.unlink()
    except PermissionError:
        pass

    assert not errors, "Schema drift detected:\n" + "\n".join(errors)
