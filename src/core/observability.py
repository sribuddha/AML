from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from aml_observability import (
    init as _init_backend,
    get_callbacks,
    wrap_openai,
    wrap_gemini,
    shutdown as _shutdown,
)


def _load_env() -> None:
    _dotenv = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(_dotenv)


def setup() -> None:
    _load_env()
    _init_backend(
        provider=os.environ.get("OBSERVABILITY_PROVIDER", "none"),
        host=os.environ.get("LANGFUSE_HOST", "http://127.0.0.1:3000"),
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
    )


def get_langgraph_callbacks() -> Sequence[Any]:
    return get_callbacks()


def wrap_openai_client(client: Any) -> Any:
    return wrap_openai(client)


def wrap_gemini_client(client: Any) -> Any:
    return wrap_gemini(client)


def shutdown() -> None:
    _shutdown()
