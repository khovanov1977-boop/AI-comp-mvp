"""Small per-IP limit for public authentication endpoints (one API worker)."""

from collections import deque
from math import ceil
from threading import RLock
from time import monotonic


class AuthRateLimiter:
    def __init__(self) -> None:
        self._attempts: dict[tuple[str, str], deque[float]] = {}
        self._lock = RLock()

    def retry_after(self, action: str, client_ip: str, limit: int, window_seconds: int,
                    now: float | None = None) -> int:
        current = monotonic() if now is None else now
        key = (action, client_ip)
        with self._lock:
            if len(self._attempts) > 10_000:
                self._attempts = {
                    item: times for item, times in self._attempts.items()
                    if times and times[-1] > current - 3600
                }
            attempts = self._attempts.setdefault(key, deque())
            while attempts and attempts[0] <= current - window_seconds:
                attempts.popleft()
            if len(attempts) >= limit:
                return max(1, ceil(attempts[0] + window_seconds - current))
            attempts.append(current)
            return 0


auth_rate_limiter = AuthRateLimiter()
