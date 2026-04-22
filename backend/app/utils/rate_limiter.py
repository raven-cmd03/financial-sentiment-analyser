import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class TokenBucketLimiter:
    """Async-safe token-bucket rate limiter.

    Tokens refill at *rate* tokens per second up to *max_tokens*.
    ``acquire()`` blocks until a token is available.
    """

    def __init__(self, rate: float, max_tokens: int):
        self.rate = rate
        self.max_tokens = max_tokens
        self.tokens: float = float(max_tokens)
        self.last_refill: float = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
        self.last_refill = now

    async def acquire(self) -> None:
        """Wait until a token is available, then consume one."""
        while True:
            async with self._lock:
                self._refill()
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return

            wait_time = (1.0 - self.tokens) / self.rate if self.rate > 0 else 0.1
            logger.debug("Rate limiter: waiting %.3fs for token", wait_time)
            await asyncio.sleep(wait_time)
