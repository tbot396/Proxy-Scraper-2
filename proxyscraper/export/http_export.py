from __future__ import annotations

import logging

import httpx

from proxyscraper.core.models import Proxy
from proxyscraper.export.file_export import FileExporter

logger = logging.getLogger(__name__)


class HTTPExporter:
    def __init__(
        self,
        url: str,
        method: str = "POST",
        auth_header: str = "",
        timeout: float = 30.0,
    ) -> None:
        self.url = url
        self.method = method.upper()
        self.auth_header = auth_header
        self.timeout = timeout

    async def export(self, proxies: list[Proxy]) -> None:
        data = FileExporter().to_string(proxies, "json")
        headers: dict[str, str] = {"Content-Type": "application/json"}

        if self.auth_header:
            key, _, value = self.auth_header.partition(": ")
            if key and value:
                headers[key] = value

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if self.method == "POST":
                    resp = await client.post(self.url, content=data, headers=headers)
                elif self.method == "PUT":
                    resp = await client.put(self.url, content=data, headers=headers)
                else:
                    logger.error("Unsupported HTTP method: %s", self.method)
                    return

                resp.raise_for_status()
                logger.info(
                    "HTTP export: %d proxies sent to %s (status %d)",
                    len(proxies), self.url, resp.status_code,
                )
        except httpx.HTTPError as e:
            logger.error("HTTP export failed: %s", e)
            raise
