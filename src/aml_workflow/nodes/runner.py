from __future__ import annotations

import asyncio
from typing import Any, Callable

from langgraph.errors import GraphInterrupt
from sqlalchemy.ext.asyncio import AsyncSession

from src.aml_workflow.state import WorkflowState
from src.bff.logger import logger


MAX_RETRIES = 3

_LIBRARY_TRANSIENT_NAMES = {
    "OperationalError",
    "ConnectError",
    "APITimeoutError",
    "APIConnectionError",
    "RateLimitError",
    "InternalServerError",
}


def _is_transient(e: Exception) -> bool:
    if isinstance(e, (TimeoutError, ConnectionError)):
        return True
    return any(cls.__name__ in _LIBRARY_TRANSIENT_NAMES for cls in type(e).__mro__)


async def run_node(state: WorkflowState, db: AsyncSession, step_name: str, fn: Callable) -> dict:
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            result = await fn(state)
            return result
        except GraphInterrupt:
            raise
        except Exception as e:
            last_exc = e
            if _is_transient(e) and attempt < MAX_RETRIES:
                await db.rollback()
                logger.warning(
                    "%s failed (attempt %d/%d): %s: %s",
                    step_name, attempt + 1, MAX_RETRIES + 1,
                    type(e).__name__, e,
                )
                await asyncio.sleep(2 ** attempt)
            else:
                break

    logger.error(
        "%s failed permanently: %s: %s",
        step_name, type(last_exc).__name__, last_exc,
        exc_info=last_exc,
    )
    raise last_exc
