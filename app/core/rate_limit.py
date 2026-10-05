"""Tiny in-memory throttle for failed logins (per client IP + email).

In memory means it resets on restart and isn't shared between workers; behind several workers use Redis.
"""
import time
from collections import defaultdict, deque
from threading import Lock


class LoginThrottle:
    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def retry_after(self, key: str, max_attempts: int, window: int) -> int:
        """Seconds to wait if `key` is locked out, else 0."""
        with self._lock:
            q = self._failures.get(key)
            if q is None:
                return 0
            cutoff = time.monotonic() - window
            while q and q[0] < cutoff:
                q.popleft()
            if not q:
                del self._failures[key]  # don't keep empty keys around forever
                return 0
            if len(q) < max_attempts:
                return 0
            return int(q[0] + window - time.monotonic()) + 1

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._failures[key].append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._failures.clear()
            else:
                self._failures.pop(key, None)


login_throttle = LoginThrottle()


class SlidingWindowLimiter:
    """At most `max_calls` per `window` seconds for each key (e.g. a user id). In memory, like LoginThrottle."""

    def __init__(self) -> None:
        self._calls: dict[int, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def retry_after(self, key: int, max_calls: int, window: int = 3600) -> int:
        """Records a call and returns 0, or returns the seconds to wait (without recording) when over the limit."""
        now = time.monotonic()
        with self._lock:
            q = self._calls[key]
            while q and q[0] < now - window:
                q.popleft()
            if len(q) >= max_calls:
                return int(q[0] + window - now) + 1
            q.append(now)
            return 0

    def reset(self) -> None:
        with self._lock:
            self._calls.clear()


assistant_limiter = SlidingWindowLimiter()
