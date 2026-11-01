"""Security middleware: simple in-memory rate limiting.

Suitable for the single-process Phase 2 deployment. For multi-worker production
deployments this must be replaced by a shared store (e.g. Redis) — documented in
PRODUCTION.md scope. Exempt: /docs, /openapi.json, static files.
"""
import time
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

WINDOW_SECONDS = 60
DEFAULT_LIMIT = 120
WRITE_LIMIT = 40
AUTH_LIMIT = 15  # per IP per minute, /auth/* — blunts credential stuffing

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits = defaultdict(deque)

    def _limit_for(self, method: str, path: str) -> int:
        if path.startswith("/api/v1/auth/"):
            return AUTH_LIMIT
        return WRITE_LIMIT if method in ("POST", "PUT", "DELETE", "PATCH") else DEFAULT_LIMIT

    async def dispatch(self, request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        key = request.client.host if request.client else "unknown"
        kind = "auth" if path.startswith("/api/v1/auth/") else "general"
        limit = self._limit_for(request.method, path)
        now = time.time()
        bucket = self._hits[(kind, key)]
        while bucket and bucket[0] < now - WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= limit:
            return JSONResponse({"detail": "Rate limit exceeded. Try again shortly."},
                                status_code=429, headers={"Retry-After": str(WINDOW_SECONDS)})
        bucket.append(now)
        return await call_next(request)
