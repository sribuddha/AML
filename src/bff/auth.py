from __future__ import annotations

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.bff.config import get_api_key


class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        if path == "/api/health":
            return await call_next(request)

        api_key = get_api_key()
        if not api_key:
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if not auth.startswith(f"Bearer {api_key}"):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        return await call_next(request)
