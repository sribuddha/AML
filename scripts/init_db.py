from pathlib import Path

from alembic import command
from alembic.config import Config


def main():
    alembic_cfg = Config(Path(__file__).resolve().parent.parent / "src" / "bff" / "alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("Database initialized successfully.")


if __name__ == "__main__":
    main()
