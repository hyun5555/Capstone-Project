import threading
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request

from app.config import ANALYSIS_RATE_LIMIT_PER_MINUTE, API_RATE_LIMIT_PER_MINUTE, AUTH_RATE_LIMIT_PER_MINUTE
from app.models.user import User
from app.services.auth import get_current_user


class _RateLimiter:
    """shortcut: process-local limits assume one API worker; use Redis before horizontal scaling."""

    def __init__(self, limit: int, window_seconds: int = 60):
        self.limit = limit
        self.window_seconds = window_seconds
        self._events = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(self.window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=429,
                    detail="요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
                    headers={"Retry-After": str(retry_after)},
                )
            events.append(now)


_auth_limiter = _RateLimiter(AUTH_RATE_LIMIT_PER_MINUTE)
_api_limiter = _RateLimiter(API_RATE_LIMIT_PER_MINUTE)
_analysis_limiter = _RateLimiter(ANALYSIS_RATE_LIMIT_PER_MINUTE)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",", 1)[0].strip() if forwarded else (request.client.host if request.client else "unknown")


async def auth_rate_limit(request: Request) -> None:
    _auth_limiter.check(_client_ip(request))


async def public_rate_limit(request: Request) -> None:
    _api_limiter.check(f"public:{_client_ip(request)}")


async def protected_rate_limit(
    request: Request,
    user: User = Depends(get_current_user),
) -> None:
    _api_limiter.check(user.user_id)


async def analysis_rate_limit(
    request: Request,
    user: User = Depends(get_current_user),
) -> None:
    _analysis_limiter.check(user.user_id)
