from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Single-node guard; production deployments should move counters to Redis."""

    def __init__(self, app, global_limit: int = 100, ai_limit: int = 10) -> None:
        super().__init__(app)
        self.global_limit = global_limit
        self.ai_limit = ai_limit
        self.windows: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in {"/health", "/metrics"}:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        is_ai = any(
            part in request.url.path
            for part in ("/script/generate", "/generate-image", "/production/start")
        )
        scope = "ai" if is_ai else "global"
        limit = self.ai_limit if is_ai else self.global_limit
        key = f"{client}:{scope}"
        now = time.monotonic()
        values = self.windows[key]
        while values and values[0] <= now - 60:
            values.popleft()
        if len(values) >= limit:
            return Response(
                content='{"error":{"code":"RATE_LIMITED","message":"Too many requests"}}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )
        values.append(now)
        return await call_next(request)
