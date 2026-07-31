from __future__ import annotations

import logging

import httpx

from proxyscraper.core.config import AnonymityConfig
from proxyscraper.core.models import AnonymityLevel, Proxy

logger = logging.getLogger(__name__)

_PROXY_HEADERS = [
    "via", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto",
    "forwarded", "x-real-ip", "proxy-connection", "x-proxy-id",
    "x-bluecoat-via",
]


class AnonymityChecker:
    def __init__(self, config: AnonymityConfig) -> None:
        self.config = config
        self._origin_ip: str | None = None

    async def get_origin_ip(self) -> str:
        if self._origin_ip:
            return self._origin_ip
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(self.config.echo_url)
                resp.raise_for_status()
                data = resp.json()
                headers = {k.lower(): v for k, v in data.get("headers", {}).items()}
                self._origin_ip = headers.get("x-forwarded-for", "").split(",")[0].strip()
                if not self._origin_ip:
                    resp2 = await client.get("http://httpbin.org/ip")
                    self._origin_ip = resp2.json().get("origin", "").split(",")[0].strip()
        except Exception as e:
            logger.error("Failed to determine origin IP: %s", e)
            self._origin_ip = ""
        return self._origin_ip or ""

    async def check(self, proxy: Proxy, timeout: float = 10.0) -> str | None:
        origin_ip = await self.get_origin_ip()
        if not origin_ip:
            logger.warning("Cannot check anonymity without origin IP")
            return None

        try:
            async with httpx.AsyncClient(
                proxy=f"http://{proxy.address}",
                timeout=timeout,
            ) as client:
                resp = await client.get(self.config.echo_url)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.debug("Anonymity check failed for %s: %s", proxy.address, e)
            return None

        headers = {k.lower(): v for k, v in data.get("headers", {}).items()}

        ip_visible = any(
            origin_ip in headers.get(h, "") for h in _PROXY_HEADERS
        )
        proxy_detected = any(h in headers for h in _PROXY_HEADERS)

        if ip_visible:
            level = AnonymityLevel.TRANSPARENT.value
        elif proxy_detected:
            level = AnonymityLevel.ANONYMOUS.value
        else:
            level = AnonymityLevel.ELITE.value

        proxy.anonymity = level
        return level
