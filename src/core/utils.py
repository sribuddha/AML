from datetime import datetime, UTC


def now() -> str:
    return datetime.now(UTC).isoformat()
