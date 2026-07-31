from __future__ import annotations

import logging
from datetime import datetime
from urllib.parse import urlparse

from proxyscraper.core.models import Source
from proxyscraper.core.storage import Storage

logger = logging.getLogger(__name__)


class SourceRegistry:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def add_source(self, url: str) -> bool:
        normalized = self._normalize_url(url)
        if not normalized:
            return False
        existing = self.storage.get_sources(enabled_only=False)
        if any(s.url == normalized for s in existing):
            return False
        self.storage.upsert_source(Source(url=normalized))
        logger.info("Added source: %s", normalized)
        return True

    def add_sources(self, urls: list[str]) -> int:
        added = 0
        for url in urls:
            if self.add_source(url):
                added += 1
        return added

    def get_enabled_sources(self) -> list[Source]:
        return self.storage.get_sources(enabled_only=True)

    def get_due_sources(self, max_age_hours: int = 24) -> list[Source]:
        return self.storage.get_due_sources(max_age_hours)

    def mark_crawled(self, url: str, proxy_count: int = 0) -> None:
        source = Source(
            url=url,
            last_crawled=datetime.utcnow(),
            proxy_count=proxy_count,
            enabled=True,
        )
        self.storage.upsert_source(source)

    def disable_source(self, url: str) -> None:
        source = Source(url=url, enabled=False)
        self.storage.upsert_source(source)

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = url.strip()
        if not url:
            return ""
        if not url.startswith(("http://", "https://")):
            url = "http://" + url
        parsed = urlparse(url)
        if not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
