from typing import Any
from collections.abc import Sequence

from aml_observability.base import ObservabilityBackend


class NullBackend(ObservabilityBackend):
    def get_name(self) -> str:
        return "none"

    def get_callbacks(self) -> Sequence[Any]:
        return []

    def wrap_openai(self, client: Any) -> Any:
        return client

    def wrap_gemini(self, client: Any) -> Any:
        return client

    def shutdown(self) -> None:
        pass
