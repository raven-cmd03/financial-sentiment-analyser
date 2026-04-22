import asyncio
import logging
import time
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """Rate limiter using the token bucket algorithm."""

    def __init__(self, rate: float, period: float = 1.0) -> None:
        self.rate = rate
        self.period = period
        self.max_tokens = rate
        self._tokens = rate
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self.max_tokens,
                self._tokens + elapsed * (self.rate / self.period),
            )
            self._last_refill = now

            if self._tokens < 1:
                wait_time = (1 - self._tokens) * (self.period / self.rate)
                logger.debug("Rate limiter: waiting %.2fs for token", wait_time)
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1


class CircuitBreaker:
    """Circuit breaker that opens after consecutive failures and resets after a timeout."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> str:
        if self._state == self.OPEN:
            if time.monotonic() - self._last_failure_time >= self.reset_timeout:
                self._state = self.HALF_OPEN
                logger.info("Circuit breaker transitioned to HALF_OPEN")
        return self._state

    def record_success(self) -> None:
        self._failure_count = 0
        if self._state == self.HALF_OPEN:
            self._state = self.CLOSED
            logger.info("Circuit breaker CLOSED after successful request")

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._failure_count >= self.failure_threshold:
            self._state = self.OPEN
            logger.warning(
                "Circuit breaker OPENED after %d consecutive failures",
                self._failure_count,
            )

    def allow_request(self) -> bool:
        current = self.state
        if current == self.CLOSED:
            return True
        if current == self.HALF_OPEN:
            return True
        return False


class BaseAPIClient(ABC):
    """Abstract base class for all API clients with resilience patterns."""

    MAX_RETRIES = 3
    BACKOFF_BASE = 2.0
    BACKOFF_MAX = 30.0

    def __init__(
        self,
        *,
        rate_limit: float = 10.0,
        rate_period: float = 1.0,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        timeout: float = 30.0,
    ) -> None:
        self._client = httpx.AsyncClient(timeout=timeout)
        self._rate_limiter = TokenBucketRateLimiter(rate=rate_limit, period=rate_period)
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            reset_timeout=reset_timeout,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute an HTTP request with rate limiting, circuit breaker, and retry."""
        if not self._circuit_breaker.allow_request():
            raise RuntimeError(
                f"Circuit breaker is OPEN — requests to {url} are blocked"
            )

        last_exc: Exception | None = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            await self._rate_limiter.acquire()
            try:
                logger.debug("Attempt %d: %s %s", attempt, method.upper(), url)
                response = await self._client.request(method, url, **kwargs)
                response.raise_for_status()
                self._circuit_breaker.record_success()
                return response

            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_exc = exc
                self._circuit_breaker.record_failure()
                logger.warning(
                    "Request failed (attempt %d/%d): %s",
                    attempt,
                    self.MAX_RETRIES,
                    exc,
                )

                if attempt < self.MAX_RETRIES:
                    delay = min(
                        self.BACKOFF_BASE ** attempt,
                        self.BACKOFF_MAX,
                    )
                    logger.debug("Backing off %.1fs before retry", delay)
                    await asyncio.sleep(delay)

        raise last_exc  # type: ignore[misc]

    @abstractmethod
    async def fetch_news(self, query: str, max_results: int = 10) -> list[dict]:
        """Fetch financial news articles matching the query."""
        ...
