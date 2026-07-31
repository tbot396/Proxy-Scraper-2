from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from proxyscraper.core.config import HarvestConfig
from proxyscraper.core.events import EventBus, EventType
from proxyscraper.core.models import Proxy
from proxyscraper.core.search_engines.base_adapter import BaseSearchAdapter
from proxyscraper.core.storage import Storage
from proxyscraper.harvest.extractor import extract_from_html, extract_proxies
from proxyscraper.harvest.source_registry import SourceRegistry

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0",
]


class SearchCrawler:
    def __init__(
        self,
        config: HarvestConfig,
        storage: Storage,
        source_registry: SourceRegistry,
        event_bus: EventBus | None = None,
    ) -> None:
        self.config = config
        self.storage = storage
        self.source_registry = source_registry
        self.event_bus = event_bus
        self._domain_last_request: dict[str, float] = {}
        self._robots_cache: dict[str, RobotFileParser] = {}
        self._ua_index = 0
        self._running = False

    @property
    def _user_agent(self) -> str:
        ua = _USER_AGENTS[self._ua_index % len(_USER_AGENTS)]
        self._ua_index += 1
        return ua

    async def run(self, queries: list[str], engines: list[str] | None = None) -> int:
        self._running = True
        engines = engines or self.config.search.engines
        total_found = 0

        for engine_name in engines:
            if not self._running:
                break
            try:
                adapter = BaseSearchAdapter.get_adapter(engine_name)
            except ValueError as e:
                logger.warning("%s", e)
                continue

            for query in queries:
                if not self._running:
                    break
                logger.info("Searching '%s' via %s", query, engine_name)
                try:
                    urls = await adapter.search(query, self.config.search.max_results_per_query)
                except Exception as e:
                    logger.error("Search failed for '%s' on %s: %s", query, engine_name, e)
                    continue

                for url in urls:
                    if not self._running:
                        break
                    self.source_registry.add_source(url)
                    count = await self._crawl_url(url)
                    total_found += count

                    if self.event_bus:
                        self.event_bus.emit(
                            EventType.HARVEST_PROGRESS,
                            url=url, count=count, total=total_found,
                        )

        if self.event_bus:
            self.event_bus.emit(EventType.HARVEST_COMPLETE, total=total_found)

        logger.info("Harvesting complete: %d proxies found", total_found)
        self._running = False
        return total_found

    async def crawl_sources(self) -> int:
        self._running = True
        sources = self.source_registry.get_due_sources(
            max_age_hours=self.config.search.freshness_days * 24
        )
        total_found = 0

        for source in sources:
            if not self._running:
                break
            count = await self._crawl_url(source.url)
            self.source_registry.mark_crawled(source.url, count)
            total_found += count

        self._running = False
        return total_found

    def stop(self) -> None:
        self._running = False

    async def _crawl_url(self, url: str) -> int:
        domain = urlparse(url).netloc

        if self.config.crawl.respect_robots and not await self._check_robots(url):
            logger.debug("Blocked by robots.txt: %s", url)
            return 0

        await self._rate_limit(domain)

        try:
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={"User-Agent": self._user_agent},
            ) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                content = resp.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 503):
                logger.warning("Rate limited at %s, backing off", url)
                await asyncio.sleep(self.config.crawl.request_delay_seconds * 3)
            else:
                logger.debug("HTTP error for %s: %s", url, e)
            return 0
        except httpx.HTTPError as e:
            logger.debug("Request failed for %s: %s", url, e)
            return 0

        content_type = resp.headers.get("content-type", "")
        if "html" in content_type:
            pairs = extract_from_html(content, url)
        else:
            pairs = extract_proxies(content, url)

        if not pairs:
            return 0

        proxies = [
            Proxy(ip=ip, port=port, source_url=url, first_seen=datetime.utcnow())
            for ip, port in pairs
        ]
        self.storage.upsert_proxies(proxies)

        if self.event_bus:
            for p in proxies:
                self.event_bus.emit(EventType.PROXY_FOUND, proxy=p)

        return len(proxies)

    async def _rate_limit(self, domain: str) -> None:
        now = time.monotonic()
        last = self._domain_last_request.get(domain, 0)
        delay = self.config.crawl.request_delay_seconds
        elapsed = now - last
        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._domain_last_request[domain] = time.monotonic()

    async def _check_robots(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        if robots_url not in self._robots_cache:
            rp = RobotFileParser()
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.get(robots_url)
                    if resp.status_code == 200:
                        rp.parse(resp.text.splitlines())
                    else:
                        rp.allow_all = True
            except httpx.HTTPError:
                rp.allow_all = True
            self._robots_cache[robots_url] = rp

        rp = self._robots_cache[robots_url]
        return rp.can_fetch("*", url)
