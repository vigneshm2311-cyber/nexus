import asyncio
import time

class AsyncRateLimiter:
    def __init__(self, calls_per_second: float = 1.0):
        self.min_interval = 1.0 / calls_per_second
        self._lock        = asyncio.Lock()
        self._last_call   = 0.0

    async def acquire(self):
        async with self._lock:
            now     = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self.min_interval:
                await asyncio.sleep(self.min_interval - elapsed)
            self._last_call = time.monotonic()
