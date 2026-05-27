from __future__ import annotations

from typing import Any
from collections.abc import Sequence

from aml_observability._null import NullBackend


_BACKEND: Any = None


def get_name() -> str:
    _ensure()
    return _BACKEND.get_name()


def get_callbacks() -> Sequence[Any]:
    _ensure()
    return _BACKEND.get_callbacks()


def wrap_openai(client: Any) -> Any:
    _ensure()
    return _BACKEND.wrap_openai(client)


def wrap_gemini(client: Any) -> Any:
    _ensure()
    return _BACKEND.wrap_gemini(client)


def shutdown() -> None:
    global _BACKEND
    if _BACKEND is not None:
        _BACKEND.shutdown()
    _BACKEND = None


def init(
    provider: str = "none",
    host: str = "",
    public_key: str = "",
    secret_key: str = "",
) -> None:
    global _BACKEND

    if _BACKEND is not None:
        return

    if provider == "langfuse":
        from aml_observability._langfuse import LangfuseBackend

        _BACKEND = LangfuseBackend(
            host=host or "http://localhost:3000",
            public_key=public_key,
            secret_key=secret_key,
        )
    else:
        _BACKEND = NullBackend()


def _ensure() -> None:
    if _BACKEND is None:
        init()
