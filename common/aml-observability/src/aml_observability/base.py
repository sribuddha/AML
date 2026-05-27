from typing import Any, Protocol
from collections.abc import Sequence


class ObservabilityBackend(Protocol):
    def get_name(self) -> str:
        ...

    def get_callbacks(self) -> Sequence[Any]:
        ...

    def wrap_openai(self, client: Any) -> Any:
        ...

    def wrap_gemini(self, client: Any) -> Any:
        ...

    def shutdown(self) -> None:
        ...
