from __future__ import annotations

import asyncio
import logging
import time
from itertools import cycle

import httpx

from proxyscraper.core.config import ServerConfig
from proxyscraper.core.events import EventBus, EventType
from proxyscraper.core.models import Proxy, RotationStrategy
from proxyscraper.core.storage import Storage

logger = logging.getLogger(__name__)


class ProxyPool:
    def __init__(self, proxies: list[Proxy], strategy: RotationStrategy, sticky_ttl: int = 300) -> None:
        self.proxies = list(proxies)
        self.strategy = strategy
        self.sticky_ttl = sticky_ttl
        self._cycle = cycle(range(len(self.proxies))) if self.proxies else iter([])
        self._index = 0
        self._sticky_map: dict[str, tuple[Proxy, float]] = {}
        self._failed: set[str] = set()
        self._current: Proxy | None = None

    def get_proxy(self, client_addr: str = "") -> Proxy | None:
        if not self.proxies:
            return None

        active = [p for p in self.proxies if p.address not in self._failed]
        if not active:
            self._failed.clear()
            active = list(self.proxies)
            if not active:
                return None

        if self.strategy == RotationStrategy.PER_REQUEST:
            self._index = (self._index + 1) % len(active)
            return active[self._index]

        if self.strategy == RotationStrategy.STICKY and client_addr:
            now = time.monotonic()
            if client_addr in self._sticky_map:
                proxy, expires = self._sticky_map[client_addr]
                if now < expires and proxy.address not in self._failed:
                    return proxy
            proxy = active[self._index % len(active)]
            self._index += 1
            self._sticky_map[client_addr] = (proxy, now + self.sticky_ttl)
            return proxy

        if self.strategy == RotationStrategy.ON_FAILURE:
            if self._current and self._current.address not in self._failed:
                return self._current
            self._current = active[0]
            return self._current

        return active[0]

    def mark_failed(self, proxy: Proxy) -> None:
        self._failed.add(proxy.address)
        logger.info("Marked %s as failed (%d failed total)", proxy.address, len(self._failed))

    def update_proxies(self, proxies: list[Proxy]) -> None:
        self.proxies = list(proxies)
        self._failed = {addr for addr in self._failed if any(p.address == addr for p in self.proxies)}
        self._index = 0

    @property
    def active_count(self) -> int:
        return len([p for p in self.proxies if p.address not in self._failed])


class ProxyServer:
    def __init__(
        self,
        config: ServerConfig,
        storage: Storage,
        event_bus: EventBus | None = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.event_bus = event_bus
        self._server: asyncio.Server | None = None
        self._running = False
        self._pool: ProxyPool | None = None

    async def start(self) -> None:
        proxies = self.storage.get_proxies(
            alive_only=True,
            require_tags=self.config.upstream_filter.require_tags or None,
            exclude_tags=self.config.upstream_filter.exclude_tags or None,
        )

        strategy = RotationStrategy(self.config.rotation)
        self._pool = ProxyPool(proxies, strategy, self.config.sticky_ttl_seconds)

        self._server = await asyncio.start_server(
            self._handle_client,
            self.config.listen_host,
            self.config.listen_port,
        )
        self._running = True

        if self.event_bus:
            self.event_bus.emit(
                EventType.SERVER_STARTED,
                host=self.config.listen_host,
                port=self.config.listen_port,
                pool_size=len(proxies),
            )

        logger.info(
            "Proxy server started on %s:%d with %d upstreams (%s rotation)",
            self.config.listen_host, self.config.listen_port,
            len(proxies), self.config.rotation,
        )

        asyncio.create_task(self._health_loop())

        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self.event_bus:
            self.event_bus.emit(EventType.SERVER_STOPPED)
        logger.info("Proxy server stopped")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        client_addr = writer.get_extra_info("peername")
        client_ip = client_addr[0] if client_addr else ""

        try:
            first_line = await asyncio.wait_for(reader.readline(), timeout=10)
            if not first_line:
                return

            line = first_line.decode("utf-8", errors="replace").strip()
            parts = line.split()
            if len(parts) < 3:
                return

            method = parts[0].upper()

            if method == "CONNECT":
                await self._handle_connect(reader, writer, line, client_ip)
            else:
                await self._handle_http(reader, writer, first_line, client_ip)

        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.debug("Client handler error: %s", e)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_connect(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        first_line: str,
        client_ip: str,
    ) -> None:
        parts = first_line.split()
        target = parts[1]
        host, _, port_str = target.partition(":")
        port = int(port_str) if port_str else 443

        # Read remaining headers
        while True:
            header_line = await asyncio.wait_for(reader.readline(), timeout=5)
            if header_line in (b"\r\n", b"\n", b""):
                break

        for attempt in range(self.config.max_retries):
            upstream = self._pool.get_proxy(client_ip) if self._pool else None
            if not upstream:
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await writer.drain()
                return

            if self.event_bus:
                self.event_bus.emit(
                    EventType.SERVER_CONNECTION,
                    client=client_ip, upstream=upstream.address, target=target,
                )

            try:
                up_reader, up_writer = await asyncio.wait_for(
                    asyncio.open_connection(upstream.ip, upstream.port),
                    timeout=self.config.sticky_ttl_seconds,
                )

                up_writer.write(f"CONNECT {target} HTTP/1.1\r\nHost: {target}\r\n\r\n".encode())
                await up_writer.drain()

                response = await asyncio.wait_for(up_reader.readline(), timeout=10)
                if b"200" in response:
                    # Drain upstream headers
                    while True:
                        h = await asyncio.wait_for(up_reader.readline(), timeout=5)
                        if h in (b"\r\n", b"\n", b""):
                            break

                    writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    await writer.drain()

                    await asyncio.gather(
                        self._pipe(reader, up_writer),
                        self._pipe(up_reader, writer),
                    )
                    return
                else:
                    up_writer.close()
                    self._pool.mark_failed(upstream)

            except Exception:
                if self._pool:
                    self._pool.mark_failed(upstream)

        writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        await writer.drain()

    async def _handle_http(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        first_line: bytes,
        client_ip: str,
    ) -> None:
        headers = bytearray(first_line)
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            headers.extend(line)
            if line in (b"\r\n", b"\n", b""):
                break

        for attempt in range(self.config.max_retries):
            upstream = self._pool.get_proxy(client_ip) if self._pool else None
            if not upstream:
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                await writer.drain()
                return

            try:
                up_reader, up_writer = await asyncio.wait_for(
                    asyncio.open_connection(upstream.ip, upstream.port),
                    timeout=10,
                )

                up_writer.write(bytes(headers))
                await up_writer.drain()

                response = await asyncio.wait_for(up_reader.read(65536), timeout=15)
                if response:
                    writer.write(response)
                    await writer.drain()

                    while True:
                        chunk = await asyncio.wait_for(up_reader.read(65536), timeout=10)
                        if not chunk:
                            break
                        writer.write(chunk)
                        await writer.drain()

                up_writer.close()
                return

            except Exception:
                if self._pool:
                    self._pool.mark_failed(upstream)

        writer.write(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
        await writer.drain()

    @staticmethod
    async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                data = await asyncio.wait_for(reader.read(65536), timeout=60)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except (asyncio.TimeoutError, ConnectionError, OSError):
            pass
        finally:
            try:
                writer.close()
            except Exception:
                pass

    async def _health_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.config.health_check_interval_seconds)
            if not self._running or not self._pool:
                break

            proxies = self.storage.get_proxies(
                alive_only=True,
                require_tags=self.config.upstream_filter.require_tags or None,
                exclude_tags=self.config.upstream_filter.exclude_tags or None,
            )
            self._pool.update_proxies(proxies)
            logger.debug("Health check: pool updated with %d proxies", len(proxies))
