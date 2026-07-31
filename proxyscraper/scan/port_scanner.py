from __future__ import annotations

import logging
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from proxyscraper.core.config import ScanConfig
from proxyscraper.core.events import EventBus, EventType
from proxyscraper.core.models import Proxy

logger = logging.getLogger(__name__)


class PortScanner:
    def __init__(
        self,
        config: ScanConfig,
        event_bus: EventBus | None = None,
    ) -> None:
        self.config = config
        self.event_bus = event_bus
        self._running = False
        self._rate_lock = threading.Lock()
        self._request_times: list[float] = []

    def scan_single(self, ip: str, port: int) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config.connect_timeout_seconds)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except (OSError, socket.error):
            return False

    def scan_batch(self, proxies: list[Proxy]) -> list[Proxy]:
        self._running = True
        alive: list[Proxy] = []
        total = len(proxies)
        completed = 0

        logger.info("Scanning %d proxies with %d workers", total, self.config.max_workers)

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as pool:
            future_to_proxy = {}
            for proxy in proxies:
                if not self._running:
                    break
                self._throttle()
                fut = pool.submit(self._scan_with_retry, proxy.ip, proxy.port)
                future_to_proxy[fut] = proxy

            for fut in as_completed(future_to_proxy):
                if not self._running:
                    break
                proxy = future_to_proxy[fut]
                completed += 1

                try:
                    is_alive = fut.result()
                except Exception:
                    is_alive = False

                proxy.alive = is_alive
                if is_alive:
                    alive.append(proxy)

                if self.event_bus and completed % 50 == 0:
                    self.event_bus.emit(
                        EventType.SCAN_PROGRESS,
                        completed=completed, total=total, alive=len(alive),
                    )

        if self.event_bus:
            self.event_bus.emit(
                EventType.SCAN_COMPLETE,
                total=total, alive=len(alive),
            )

        logger.info("Scan complete: %d/%d alive", len(alive), total)
        self._running = False
        return alive

    def stop(self) -> None:
        self._running = False

    def _scan_with_retry(self, ip: str, port: int) -> bool:
        for attempt in range(self.config.retries + 1):
            if self.scan_single(ip, port):
                return True
        return False

    def _throttle(self) -> None:
        if self.config.max_connections_per_second <= 0:
            return
        with self._rate_lock:
            now = time.monotonic()
            self._request_times = [t for t in self._request_times if now - t < 1.0]
            if len(self._request_times) >= self.config.max_connections_per_second:
                sleep_time = 1.0 - (now - self._request_times[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
            self._request_times.append(time.monotonic())
