from __future__ import annotations

from typing import Any
from collections.abc import Sequence

from aml_observability import init as _init_backend, get_callbacks, wrap_openai, shutdown as _shutdown
from src.bff.config import OBSERVABILITY_PROVIDER, LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY


def setup() -> None:
    _init_backend(
        provider=OBSERVABILITY_PROVIDER,
        host=LANGFUSE_HOST,
        public_key=LANGFUSE_PUBLIC_KEY,
        secret_key=LANGFUSE_SECRET_KEY,
    )


def get_langgraph_callbacks() -> Sequence[Any]:
    return get_callbacks()


def wrap_openai_client(client: Any) -> Any:
    return wrap_openai(client)


def shutdown() -> None:
    _shutdown()
