from collections import defaultdict, deque
from datetime import datetime, timedelta
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from settings import get_settings

settings = get_settings()


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.hits = defaultdict(deque)
        self.limit = settings.rate_limit_per_minute

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=1)
        dq = self.hits[ip]
        while dq and dq[0] < window_start:
            dq.popleft()
        if len(dq) >= self.limit:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        dq.append(now)
        return await call_next(request)
