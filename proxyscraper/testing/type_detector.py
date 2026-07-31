from __future__ import annotations

import logging
import socket
import struct

import httpx

from proxyscraper.core.config import TypeDetectorConfig
from proxyscraper.core.models import Proxy

logger = logging.getLogger(__name__)


class TypeDetector:
    def __init__(self, config: TypeDetectorConfig) -> None:
        self.config = config

    async def detect(self, proxy: Proxy, timeout: float = 10.0) -> list[str]:
        protocols: list[str] = []

        if await self._test_http(proxy, timeout):
            protocols.append("http")
        if await self._test_https(proxy, timeout):
            protocols.append("https")
        if self._test_socks5(proxy, timeout):
            protocols.append("socks5")
        if self._test_socks4(proxy, timeout):
            protocols.append("socks4")

        proxy.protocols = protocols
        return protocols

    async def _test_http(self, proxy: Proxy, timeout: float) -> bool:
        try:
            async with httpx.AsyncClient(
                proxy=f"http://{proxy.address}",
                timeout=timeout,
            ) as client:
                resp = await client.get(self.config.test_url)
                return resp.status_code == 200
        except Exception:
            return False

    async def _test_https(self, proxy: Proxy, timeout: float) -> bool:
        test_url = self.config.test_url.replace("http://", "https://", 1)
        try:
            async with httpx.AsyncClient(
                proxy=f"http://{proxy.address}",
                timeout=timeout,
            ) as client:
                resp = await client.get(test_url)
                return resp.status_code == 200
        except Exception:
            return False

    def _test_socks5(self, proxy: Proxy, timeout: float) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((proxy.ip, proxy.port))

            # SOCKS5 greeting: version 5, 1 auth method (no auth)
            sock.sendall(b"\x05\x01\x00")
            resp = sock.recv(2)
            sock.close()

            # Valid SOCKS5 response: version 5, method 0 (no auth) or method 2 (user/pass)
            return len(resp) == 2 and resp[0] == 5 and resp[1] in (0, 2)
        except (OSError, socket.error):
            return False

    def _test_socks4(self, proxy: Proxy, timeout: float) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((proxy.ip, proxy.port))

            # SOCKS4 connect request to httpbin.org (93.184.216.34 as placeholder)
            dest_ip = socket.inet_aton("93.184.216.34")
            packet = struct.pack("!BBH", 4, 1, 80) + dest_ip + b"\x00"
            sock.sendall(packet)
            resp = sock.recv(8)
            sock.close()

            # Valid SOCKS4 response: null byte, status 0x5a (granted)
            return len(resp) >= 2 and resp[0] == 0 and resp[1] == 0x5A
        except (OSError, socket.error):
            return False
