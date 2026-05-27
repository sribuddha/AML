from __future__ import annotations

from typing import Any
from collections.abc import Sequence

from aml_observability.base import ObservabilityBackend


class LangfuseBackend(ObservabilityBackend):
    def __init__(self, host: str, public_key: str, secret_key: str) -> None:
        self._host = host
        self._public_key = public_key
        self._secret_key = secret_key
        self._lf: Any = None
        self._handler: Any = None
        self._handler_setup = False

    def _get_lf(self):
        if self._lf is None:
            from langfuse import Langfuse
            self._lf = Langfuse(
                host=self._host,
                public_key=self._public_key,
                secret_key=self._secret_key,
            )
        return self._lf

    def get_name(self) -> str:
        return "langfuse"

    def get_callbacks(self) -> Sequence[Any]:
        if not self._handler_setup:
            try:
                self._get_lf()
                from langfuse.langchain import CallbackHandler
                self._handler = CallbackHandler()
            except Exception:
                self._handler = None
            self._handler_setup = True
        h = self._handler
        return [h] if h is not None else []

    def wrap_openai(self, client: Any) -> Any:
        try:
            self._get_lf()
            from langfuse.openai import AsyncOpenAI as LangfuseAsyncOpenAI

            lf_client = LangfuseAsyncOpenAI(
                api_key=client.api_key,
                base_url=client.base_url if hasattr(client, "base_url") else None,
            )
            return lf_client
        except Exception:
            return client

    def wrap_gemini(self, client: Any) -> Any:
        return client

    def shutdown(self) -> None:
        try:
            if self._lf is not None:
                self._lf.flush()
        except Exception:
            pass
