"""A small in-memory attempt limiter for login and signup.

It lives in the process, so it resets on restart and is per-instance. That is
enough for a single-instance alpha; move it to Redis before running several
instances.
"""
import threading
import time
from collections import defaultdict, deque
from typing import Callable


class AttemptLimiter:
    def __init__(self, max_attempts: int, window_seconds: float, clock: Callable[[], float] = time.monotonic):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._clock = clock
        self._attempts: dict = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> deque:
        attempts = self._attempts[key]
        while attempts and now - attempts[0] >= self.window_seconds:
            attempts.popleft()
        return attempts

    def allow(self, key: str) -> bool:
        """Record an attempt. False means the caller is over the limit."""
        now = self._clock()
        with self._lock:
            attempts = self._prune(key, now)
            if len(attempts) >= self.max_attempts:
                return False
            attempts.append(now)
            return True

    def retry_after(self, key: str) -> int:
        now = self._clock()
        with self._lock:
            attempts = self._prune(key, now)
            if len(attempts) < self.max_attempts:
                return 0
            return max(1, int(self.window_seconds - (now - attempts[0])) + 1)

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._attempts.clear()
