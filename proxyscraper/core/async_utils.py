from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def run_with_semaphore(
    sem: asyncio.Semaphore,
    coro: Awaitable[T],
) -> T:
    async with sem:
        return await coro


async def retry_async(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    **kwargs: Any,
) -> T:
    last_exc: Exception | None = None
    current_delay = delay
    for attempt in range(retries + 1):
        try:
            return await fn(*args, **kwargs)
        except exceptions as e:
            last_exc = e
            if attempt < retries:
                logger.debug(
                    "Retry %d/%d for %s after %.1fs: %s",
                    attempt + 1, retries, fn.__name__, current_delay, e,
                )
                await asyncio.sleep(current_delay)
                current_delay *= backoff
    raise last_exc  # type: ignore[misc]


async def timeout_async(coro: Awaitable[T], seconds: float) -> T:
    return await asyncio.wait_for(coro, timeout=seconds)


async def gather_with_concurrency(
    limit: int,
    *coros: Awaitable[T],
) -> list[T]:
    sem = asyncio.Semaphore(limit)

    async def _wrap(c: Awaitable[T]) -> T:
        async with sem:
            return await c

    return await asyncio.gather(*[_wrap(c) for c in coros])
