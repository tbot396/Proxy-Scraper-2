from __future__ import annotations

import logging
import statistics
import time

import httpx

from proxyscraper.core.config import LatencyConfig
from proxyscraper.core.models import Proxy

logger = logging.getLogger(__name__)


class LatencyMeasurer:
    def __init__(self, config: LatencyConfig) -> None:
        self.config = config

    async def measure(self, proxy: Proxy, timeout: float = 10.0) -> int | None:
        times: list[float] = []

        async with httpx.AsyncClient(
            proxy=f"http://{proxy.address}",
            timeout=timeout,
        ) as client:
            for _ in range(self.config.num_pings):
                start = time.monotonic()
                try:
                    resp = await client.get(self.config.test_url)
                    resp.raise_for_status()
                    elapsed = (time.monotonic() - start) * 1000
                    times.append(elapsed)
                except Exception:
                    continue

        if not times:
            return None

        latency = int(statistics.median(times))
        proxy.latency_ms = latency
        return latency
