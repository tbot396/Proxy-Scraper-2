from __future__ import annotations

import logging
import re

import httpx

from .base_adapter import BaseSearchAdapter

logger = logging.getLogger(__name__)

_URL_PATTERN = re.compile(r'uddg=(https?[^&"]+)')


class DuckDuckGoSearchAdapter(BaseSearchAdapter):
    name = "duckduckgo"

    def __init__(self, **kwargs: object) -> None:
        pass

    async def search(self, query: str, max_results: int = 10) -> list[str]:
        results: list[str] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            try:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers=headers,
                )
                resp.raise_for_status()
                html = resp.text
            except httpx.HTTPError as e:
                logger.error("DuckDuckGo search error: %s", e)
                return []

            for match in _URL_PATTERN.finditer(html):
                url = match.group(1)
                from urllib.parse import unquote
                url = unquote(url)
                if url not in results:
                    results.append(url)
                    if len(results) >= max_results:
                        break

        logger.info("DuckDuckGo returned %d results for '%s'", len(results), query)
        return results[:max_results]
